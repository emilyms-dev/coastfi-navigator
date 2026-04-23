"""Auth unit tests — Phase 4.

Tests for app/auth/users.py. DB calls are mocked so these tests do not
require a running database. Flask request context is provided via a
minimal test Flask app.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import bcrypt
import pytest
from flask import Flask

from app.auth.users import (
    UNAUTHENTICATED_STATE,
    build_auth_store_payload,
    get_current_user,
    login_user,
    logout_user,
    register_user,
)
from app.db.models import User

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def flask_app() -> Flask:
    """Minimal Flask app for request-context tests."""
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def mock_user() -> User:
    """A User instance with a known bcrypt hash for password 'ValidPass1'."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "test@example.com"
    user.password_hash = bcrypt.hashpw(b"ValidPass1", bcrypt.gensalt()).decode()
    return user


# ── Registration tests ────────────────────────────────────────────────────────


def test_register_hashes_password(mock_user) -> None:
    """Stored hash must not equal plaintext and must verify correctly."""
    with patch("app.auth.users.crud.create_user", return_value=mock_user):
        user = register_user("alice@example.com", "ValidPass1")

    assert user.password_hash != "ValidPass1"
    assert bcrypt.checkpw(b"ValidPass1", user.password_hash.encode())


def test_register_duplicate_email_raises() -> None:
    """Second registration with the same email must raise ValueError."""
    with patch(
        "app.auth.users.crud.create_user",
        side_effect=ValueError("already exists"),
    ):
        with pytest.raises(ValueError, match="already exists"):
            register_user("bob@example.com", "ValidPass1")


def test_register_short_password_raises() -> None:
    """Password shorter than 8 characters must raise ValueError."""
    with pytest.raises(ValueError, match="at least 8"):
        register_user("carol@example.com", "Short1")


def test_register_invalid_email_raises() -> None:
    """Malformed email must raise ValueError before touching the DB."""
    with patch("app.auth.users.crud.create_user") as mock_create:
        with pytest.raises(ValueError, match="Invalid email"):
            register_user("not-an-email", "ValidPass1")
        mock_create.assert_not_called()


# ── Login tests ───────────────────────────────────────────────────────────────


def test_login_correct_credentials(mock_user) -> None:
    """Correct email + password must return the User."""
    with patch("app.auth.users.crud.get_user_by_email", return_value=mock_user):
        result = login_user("test@example.com", "ValidPass1")

    assert result is not None
    assert result.email == "test@example.com"


def test_login_wrong_password(mock_user) -> None:
    """Wrong password must return None."""
    with patch("app.auth.users.crud.get_user_by_email", return_value=mock_user):
        result = login_user("test@example.com", "WrongPass")

    assert result is None


def test_login_unknown_email() -> None:
    """Unknown email must return None."""
    with patch("app.auth.users.crud.get_user_by_email", return_value=None):
        result = login_user("nobody@example.com", "ValidPass1")

    assert result is None


# ── Session tests ─────────────────────────────────────────────────────────────


def test_logout_clears_session(flask_app) -> None:
    """logout_user() must clear all session data."""
    with flask_app.test_request_context("/"):
        from flask import session

        session["user_id"] = 99
        assert session.get("user_id") == 99
        logout_user()
        assert len(session) == 0


def test_get_current_user_returns_user(flask_app, mock_user) -> None:
    """get_current_user() returns the User for the id stored in session."""
    with flask_app.test_request_context("/"):
        from flask import session

        session["user_id"] = mock_user.id
        with patch("app.auth.users.crud.get_user_by_id", return_value=mock_user):
            result = get_current_user()

    assert result is not None
    assert result.id == mock_user.id


def test_get_current_user_no_session_returns_none(flask_app) -> None:
    """get_current_user() returns None when no session is active."""
    with flask_app.test_request_context("/"):
        result = get_current_user()

    assert result is None


# ── Payload / constant tests ──────────────────────────────────────────────────


def test_build_auth_store_payload(mock_user) -> None:
    """Payload must contain authenticated=True and correct user fields."""
    payload = build_auth_store_payload(mock_user)

    assert payload["authenticated"] is True
    assert payload["user_id"] == mock_user.id
    assert payload["email"] == mock_user.email


def test_unauthenticated_state_constant() -> None:
    """UNAUTHENTICATED_STATE must mark session as not authenticated."""
    assert UNAUTHENTICATED_STATE["authenticated"] is False
    assert UNAUTHENTICATED_STATE["user_id"] is None
    assert UNAUTHENTICATED_STATE["email"] is None


# ── Security: password never logged ──────────────────────────────────────────


def test_password_never_logged(caplog, mock_user) -> None:
    """The literal password string must never appear in any log output."""
    secret = "ValidPass1"

    with caplog.at_level(logging.DEBUG):
        with patch("app.auth.users.crud.get_user_by_email", return_value=mock_user):
            login_user("test@example.com", secret)

        with patch("app.auth.users.crud.create_user", return_value=mock_user):
            try:
                register_user("new@example.com", secret)
            except Exception:
                pass

    assert "password" not in caplog.text.lower()
    assert secret not in caplog.text
