"""Dash application entry point.

Initializes logging, verifies database connectivity with retry logic,
constructs the Dash app, and starts the development server when invoked directly.
"""

import logging
import os
import time

import dash
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Dash app ──────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    pages_folder="pages",
    use_pages=True,
    suppress_callback_exceptions=True,
)

# Expose Flask server for WSGI deployment (e.g. gunicorn)
server = app.server

from app.layout import build_layout  # noqa: E402 — import after app is created

app.layout = build_layout()

# ── Database startup check ────────────────────────────────────────────────────

_MAX_DB_ATTEMPTS = 10
_DB_RETRY_DELAY_SECONDS = 2


def _wait_for_database() -> None:
    """Block until the database is reachable or exhaust all retry attempts.

    Uses SQLAlchemy engine.connect() so the same connection configuration
    that the rest of the app uses is exercised at startup.

    Raises:
        SystemExit: If the database is unreachable after all retry attempts.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.critical("DATABASE_URL environment variable is not set.")
        raise SystemExit(1)

    engine = create_engine(database_url)

    for attempt in range(1, _MAX_DB_ATTEMPTS + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Database connection established.")
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Database not yet reachable (attempt %d/%d): %s",
                attempt,
                _MAX_DB_ATTEMPTS,
                exc,
            )
            if attempt < _MAX_DB_ATTEMPTS:
                # time.sleep is acceptable here: this executes before the Dash
                # server starts, so there is no event loop to block.
                time.sleep(_DB_RETRY_DELAY_SECONDS)

    logger.critical(
        "Database unreachable after %d attempts. Aborting startup.",
        _MAX_DB_ATTEMPTS,
    )
    raise SystemExit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # DB check runs here so `from app.main import server` works for WSGI
    # importers without requiring a live database at import time.
    _wait_for_database()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("APP_PORT", 8050)),
        debug=os.environ.get("DASH_DEBUG", "false").lower() == "true",
    )
