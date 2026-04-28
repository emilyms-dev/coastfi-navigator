# Coast FI Navigator

A self-hostable financial independence planning tool that answers the core
Coast FI question: **how much do you need invested today so that, with zero
additional contributions, your portfolio grows to your FI number by your
target retirement age?**

---

## The Problem

Most FI calculators tell you how much to save. Coast FI Navigator tells you
when you can *stop* saving — the point at which compound growth alone carries
you to full financial independence. It visualises the full probability
distribution of outcomes through Monte Carlo simulation so you can see not
just the median path but the realistic range of scenarios.

---

## Features

- **Coast FI calculator** — instant recalculation as you type (400ms debounce,
  no submit button)
- **Monte Carlo fan chart** — 1,000-run simulation showing the 10th, 25th,
  50th, 75th, and 90th percentile portfolio paths
- **Five FI milestones** — Lean FI, Coast FI, Barista FI, Traditional FI, Fat FI,
  each with a progress bar
- **Scenario persistence** — save named plans, browse version history,
  load saved scenarios back into the calculator
- **Public share links** — share a read-only view of any saved scenario via a
  UUID-based URL (no login required to view)
- **User accounts** — email + bcrypt password auth; session-based (no JWT)
- **Self-hosted** — single `podman-compose up` deployment, no external services

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Browser (Dash / React)                             │
│  Dash Mantine Components · Plotly fan chart         │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / WebSocket (Dash callbacks)
┌────────────────────▼────────────────────────────────┐
│  App container  (Python 3.11 + Dash / Werkzeug)     │
│                                                     │
│  app/engine/         — pure FI math, Monte Carlo    │
│  app/db/crud.py      — all DB reads/writes          │
│  app/auth/users.py   — bcrypt auth, Flask session   │
│  app/callbacks/      — Dash callback orchestration  │
│  app/pages/          — page layouts (calculator,    │
│                         dashboard, share)           │
│  app/components/     — reusable UI components       │
└────────────────────┬────────────────────────────────┘
                     │ SQLAlchemy (psycopg2)
┌────────────────────▼────────────────────────────────┐
│  PostgreSQL 16 container                            │
│  users · scenarios · scenario_snapshots             │
└─────────────────────────────────────────────────────┘
```

Key design constraints:
- Engine functions are **pure** — no DB calls, no side effects
- All DB access goes through `app/db/crud.py` — no raw SQL elsewhere
- All callbacks live in `app/callbacks/` — no logic in page or layout files
- Snapshots are **append-only** — saves never modify existing rows

---

## Quick Start

### Prerequisites

- [Podman](https://podman.io/) + [podman-compose](https://github.com/containers/podman-compose)
- (macOS) `brew install podman podman-compose`

### 1. Clone and configure

```bash
git clone <repo-url>
cd coastfi-navigator
cp .env.example .env
# Edit .env — set a strong SECRET_KEY at minimum
```

### 2. Start the stack

```bash
podman-compose up --build -d
```

The app waits up to 20 seconds for PostgreSQL to be ready before starting.

### 3. Apply database migrations

```bash
podman-compose exec app alembic upgrade head
```

### 4. (Optional) Load demo data

```bash
podman-compose exec app python scripts/seed_demo.py
```

This creates a demo user (`demo@coastfi.example` / `demo1234`) with three
pre-populated scenarios. Safe to run multiple times — idempotent.

### 5. Open the app

Visit [http://localhost:8050](http://localhost:8050)

---

## Environment Variables

See `.env.example` for the full list with comments. Required variables:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session secret — use a random 32+ char string |
| `DATABASE_URL` | SQLAlchemy connection string (set automatically in the compose stack) |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | PostgreSQL database name |

Optional:

| Variable | Default | Description |
|---|---|---|
| `DASH_DEBUG` | `false` | Enable Dash hot-reload (development only) |
| `APP_PORT` | `8050` | Port the app binds to inside the container |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Development

### Running tests

```bash
# Inside the container (all deps available including dash_iconify):
podman-compose exec app pytest tests/ -v --tb=short --cov=app/engine

# On the host (hypothesis tests require: pip install hypothesis):
pytest tests/test_calculator.py tests/test_monte_carlo.py tests/test_crud.py -v
```

### Linting

```bash
ruff check app/ tests/
```

### Database migrations

```bash
# Create a new migration after changing models:
podman-compose exec app alembic revision --autogenerate -m "description"

# Apply pending migrations:
podman-compose exec app alembic upgrade head
```

### Health check

```
GET /health
```

Returns `{"status": "ok", "db": "connected"}` (200) when the database is
reachable, or `{"status": "degraded", "db": "unreachable"}` (503) otherwise.
Suitable for container `HEALTHCHECK` directives and load-balancer probes.

---

## Project Structure

```
app/
  auth/users.py         — registration, login, session helpers
  callbacks/
    auth.py             — login/register/logout Dash callbacks
    calculation.py      — debounced FI calculation callback
    persistence.py      — save/load/delete/share scenario callbacks
  components/           — reusable UI components (charts, inputs, summaries…)
  db/
    crud.py             — all database read/write operations
    models.py           — SQLAlchemy ORM models
    session.py          — SQLAlchemy session factory
  engine/
    calculator.py       — Coast FI, Traditional FI, and milestone math
    milestones.py       — milestone metadata and progress colors
    monte_carlo.py      — vectorised Monte Carlo simulation (NumPy)
  pages/
    calculator.py       — main calculator page layout
    dashboard.py        — saved scenarios dashboard
    share.py            — read-only shared scenario view
  layout.py             — root layout (MantineProvider, AppShell, dcc.Stores)
  main.py               — Dash app init, Flask routes, startup logic
migrations/             — Alembic migration scripts
scripts/
  seed_demo.py          — demo data seeder (idempotent)
tests/                  — pytest test suite
```
