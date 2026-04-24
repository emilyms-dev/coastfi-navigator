"""Dash application entry point.

Initializes logging, verifies database connectivity with retry logic,
constructs the Dash app, and starts the development server when invoked directly.
"""

import logging
import os
import time

import dash
from dotenv import load_dotenv
from flask import jsonify, request
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

# SECRET_KEY must be set — no default fallback. A missing key is a
# deployment error that should fail loudly, not silently use an insecure value.
server.secret_key = os.environ["SECRET_KEY"]

from app.layout import get_layout  # noqa: E402 — import after app is created
from app.auth import users as auth  # noqa: E402 — import after app is created
from app.callbacks import auth as _auth_callbacks  # noqa: F401, E402 — registers auth sync callback

app.layout = get_layout()

# ── Auth routes ───────────────────────────────────────────────────────────────


@server.route("/auth/register", methods=["POST"])
def _register() -> tuple:
    """Register a new user account.

    Body: {email: str, password: str}

    Returns:
        200: {"ok": true, "email": str}
        400: {"ok": false, "error": str}  — validation or duplicate email
        500: {"ok": false, "error": "Registration failed"}  — unexpected error
    """
    body = request.get_json(silent=True) or {}
    email = body.get("email", "")
    password = body.get("password", "")
    try:
        user = auth.register_user(email, password)
        from flask import session as flask_session

        flask_session["user_id"] = user.id
        return jsonify({"ok": True, "email": user.email}), 200
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception:
        logger.exception("Unexpected error during registration for %r", email)
        return jsonify({"ok": False, "error": "Registration failed"}), 500


@server.route("/auth/login", methods=["POST"])
def _login() -> tuple:
    """Authenticate a user and start a session.

    Body: {email: str, password: str}

    Returns:
        200: {"ok": true, "email": str}
        401: {"ok": false, "error": "Invalid credentials"}
    """
    body = request.get_json(silent=True) or {}
    email = body.get("email", "")
    password = body.get("password", "")
    user = auth.login_user(email, password)
    if user is None:
        return jsonify({"ok": False, "error": "Invalid credentials"}), 401
    from flask import session as flask_session

    flask_session["user_id"] = user.id
    return jsonify({"ok": True, "email": user.email}), 200


@server.route("/auth/logout", methods=["POST"])
def _logout() -> tuple:
    """End the current session.

    Returns:
        200: {"ok": true}  — always, regardless of prior auth state
    """
    auth.logout_user()
    return jsonify({"ok": True}), 200


@server.route("/auth/me", methods=["GET"])
def _me() -> tuple:
    """Return the current session's auth state.

    Returns:
        200: {"authenticated": true, "user_id": int, "email": str}
             or {"authenticated": false}
    """
    user = auth.get_current_user()
    if user is None:
        return jsonify({"authenticated": False}), 200
    return jsonify(auth.build_auth_store_payload(user)), 200

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
