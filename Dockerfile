# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Install production dependencies into a venv so the runtime stage can copy
# only the venv — dev dependencies are never present in the final image.
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools needed to compile any C extensions (e.g. psycopg2-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated venv in a predictable location
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the dependency manifest first to leverage Docker layer caching
COPY pyproject.toml ./

# Install pip then production deps from pyproject.toml — single source of truth.
# tomllib is stdlib in Python 3.11+; reads [project.dependencies] directly so
# the container always installs the same pinned constraints as the test env.
# Dev dependencies (hypothesis, black, ruff, …) are intentionally excluded.
RUN pip install --upgrade pip && \
    python -c "\
import tomllib, subprocess, sys; \
d = tomllib.load(open('pyproject.toml', 'rb')); \
subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + d['project']['dependencies'])"

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# Slim image with only the venv from the builder stage — no gcc, no dev packages.
FROM python:3.11-slim AS runtime

WORKDIR /app

# libpq is required at runtime by psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user — principle of least privilege
RUN useradd --no-create-home --shell /bin/false appuser

# Copy the venv from the builder; no dev dependencies are included
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY pyproject.toml ./

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8050

# Poll the Dash layout endpoint — it returns JSON once the app is fully initialized
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8050/_dash-layout')" || exit 1

# Run as a module so the project root (/app) is added to sys.path,
# making `from app.layout import ...` resolvable.
CMD ["python", "-m", "app.main"]
