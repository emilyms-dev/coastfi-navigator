"""SQLAlchemy session factory — Phase 3.

Provides a configured sessionmaker bound to the application's database engine.
All database operations must obtain sessions through this factory.

This module is imported at app startup. Importing it triggers a connectivity
check against the database — the app fails fast with a clear error if the DB
is unreachable rather than surfacing obscure connection errors later.
"""

from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)

_MAX_RETRIES = 10
_RETRY_DELAY_SECONDS = 2


def _get_database_url() -> str:
    """Read DATABASE_URL from the environment.

    Returns:
        The database connection string.

    Raises:
        RuntimeError: If DATABASE_URL is not set in the environment.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Copy .env.example to .env and fill in the value before starting."
        )
    return url


def get_engine() -> Engine:
    """Create and verify a SQLAlchemy engine with retry logic.

    Creates an engine against DATABASE_URL and attempts to open a test
    connection. Retries up to _MAX_RETRIES times with _RETRY_DELAY_SECONDS
    between attempts. This mirrors the startup health check in main.py so
    that any import of this module fails loudly if the DB is unreachable.

    ``pool_pre_ping=True`` instructs SQLAlchemy to test each pooled
    connection with a cheap "SELECT 1" before handing it to a caller,
    which prevents stale connections after Postgres restarts.

    Returns:
        A connected SQLAlchemy Engine.

    Raises:
        SystemExit: With exit code 1 after all retry attempts are exhausted.
    """
    database_url = _get_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection established on attempt %d.", attempt)
            return engine
        except Exception as exc:
            logger.warning(
                "Database connection attempt %d/%d failed: %s",
                attempt,
                _MAX_RETRIES,
                exc,
            )
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_SECONDS)

    logger.error(
        "Could not connect to the database after %d attempts. Exiting.",
        _MAX_RETRIES,
    )
    raise SystemExit(1)


# Module-level engine and session factory — initialised once at import time.
# Any import of this module triggers the connectivity check: fail fast, fail
# loudly rather than discovering a missing database mid-request.
engine: Engine = get_engine()

Session = sessionmaker(bind=engine, expire_on_commit=False)
