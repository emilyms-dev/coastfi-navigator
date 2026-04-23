"""Auth logic — Phase 4.

Handles user registration, login, logout, and session management using
Flask's session mechanism. Passwords are hashed with bcrypt; plaintext
passwords are never stored or logged.
"""

from __future__ import annotations

import logging
import re

import bcrypt
from flask import session

from app.db import crud
from app.db.models import User

logger = logging.getLogger(__name__)

# Regex for basic email format validation — no external library required.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Minimum password length enforced at registration.
_MIN_PASSWORD_LENGTH = 8

# Written to store-auth-state when no user is logged in.
UNAUTHENTICATED_STATE: dict = {"authenticated": False, "user_id": None, "email": None}


def register_user(email: str, password: str) -> User:
    """Register a new user account.

    Validates email format and password length, hashes the password with
    bcrypt, then persists the new user via crud.create_user().

    Args:
        email: The user's login email address.
        password: The plaintext password chosen by the user. Never stored
            or logged; only the bcrypt hash is persisted.

    Returns:
        The newly created User with its database-assigned id populated.

    Raises:
        ValueError: If email format is invalid, password is too short,
            or a user with the given email already exists.
    """
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Invalid email address: {email!r}")
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {_MIN_PASSWORD_LENGTH} characters."
        )
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    # password is not referenced after this point — only the hash is passed on.
    return crud.create_user(email, password_hash)


def login_user(email: str, password: str) -> User | None:
    """Authenticate a user by email and password.

    Deliberately does not distinguish between "email not found" and "wrong
    password" in the return value or logs — both cases return None. This
    prevents user enumeration. A dummy bcrypt check runs when the email is
    not found to keep response timing consistent.

    Args:
        email: The email to look up.
        password: The plaintext password to verify. Never stored or logged.

    Returns:
        The authenticated User on success, or None for any failure.
    """
    user = crud.get_user_by_email(email)
    if user is None:
        # Dummy check keeps timing consistent regardless of email existence.
        bcrypt.checkpw(b"dummy", bcrypt.hashpw(b"dummy", bcrypt.gensalt()))
        return None
    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return None
    return user


def get_current_user() -> User | None:
    """Return the authenticated user for the current request, or None.

    Reads user_id from the Flask session set by a prior successful login.
    Returns None if the session is empty or the stored id no longer exists.

    Returns:
        The User for session["user_id"], or None.
    """
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return crud.get_user_by_id(user_id)


def logout_user() -> None:
    """Clear the Flask session, ending the authenticated session.

    Safe to call regardless of whether a user is currently logged in.
    """
    session.clear()


def build_auth_store_payload(user: User) -> dict:
    """Build the dict written to the store-auth-state dcc.Store on login.

    Args:
        user: The authenticated User whose identity to reflect in the
            client-side auth store.

    Returns:
        A dict with keys ``authenticated``, ``user_id``, and ``email``.
    """
    return {"authenticated": True, "user_id": user.id, "email": user.email}
