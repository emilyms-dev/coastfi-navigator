"""Auth callbacks — Phase 5 (sync) + Phase 7 (login, register, logout, navbar).

sync_auth_state: reads Flask session on every navigation and keeps the
    store-auth-state dcc.Store consistent with server-side session state.

open_auth_modal: opens the auth modal when the Sign In button is clicked.
handle_login: authenticates the user, sets Flask session, updates store.
handle_register: registers a new user, sets Flask session, updates store.
handle_logout: clears Flask session, resets store, redirects to "/".
update_navbar_auth_controls: rebuilds navbar auth controls from store state.
"""

from __future__ import annotations

import logging

import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, no_update
from dash.exceptions import PreventUpdate
from flask import session as flask_session

from app.auth.users import (
    UNAUTHENTICATED_STATE,
    build_auth_store_payload,
    get_current_user,
    login_user,
    logout_user,
    register_user,
)

logger = logging.getLogger(__name__)


# ── Phase 5: sync auth state on every navigation ──────────────────────────────


@callback(
    Output("store-auth-state", "data"),
    Input("url", "pathname"),
    prevent_initial_call=False,
)
def sync_auth_state(pathname: str) -> dict:
    """Sync Flask session auth state into the Dash store on every navigation.

    Runs on every URL change (including initial page load). Ensures the
    store never goes stale if the Flask session expires or is cleared server-side.

    Args:
        pathname: The current URL path, provided by dcc.Location.

    Returns:
        Auth payload dict with authenticated, user_id, and email fields.
    """
    user = get_current_user()
    if user:
        return build_auth_store_payload(user)
    return UNAUTHENTICATED_STATE


# ── Phase 7: open modal ───────────────────────────────────────────────────────


@callback(
    Output("modal-auth", "opened"),
    Input("btn-open-auth", "n_clicks"),
    prevent_initial_call=True,
)
def open_auth_modal(n_clicks: int | None) -> bool:
    """Open the auth modal when the Sign In / Register button is clicked.

    Args:
        n_clicks: Click count from the navbar Sign In button.

    Returns:
        True to open the modal.
    """
    # prevent_initial_call=True guards against firing on page load when
    # btn-open-auth may not exist (unauthenticated users only see it).
    return True


# ── Phase 7: login ────────────────────────────────────────────────────────────


@callback(
    Output("auth-login-error", "children"),
    Output("store-auth-state", "data", allow_duplicate=True),
    Output("modal-auth", "opened", allow_duplicate=True),
    Input("btn-login", "n_clicks"),
    State("auth-login-email", "value"),
    State("auth-login-password", "value"),
    prevent_initial_call=True,
)
def handle_login(
    n_clicks: int | None,
    email: str | None,
    password: str | None,
) -> tuple:
    """Authenticate a user and update auth store on success.

    Always returns the same generic failure message regardless of whether
    the email exists — prevents user enumeration.

    Args:
        n_clicks: Click count from the Sign In button.
        email: Email value from the login form input.
        password: Password value from the login form input.

    Returns:
        Tuple of (error_children, auth_store_data, modal_opened).
    """
    if not n_clicks:
        raise PreventUpdate

    _generic_error = dmc.Text("Invalid email or password.", c="red", size="sm")

    try:
        user = login_user(email or "", password or "")
        if user is None:
            return _generic_error, no_update, no_update
        flask_session["user_id"] = user.id
        return "", build_auth_store_payload(user), False
    except Exception:
        logger.exception("Unexpected error during login callback")
        return (
            dmc.Text("Login failed. Please try again.", c="red", size="sm"),
            no_update,
            no_update,
        )


# ── Phase 7: register ─────────────────────────────────────────────────────────


@callback(
    Output("auth-register-error", "children"),
    Output("store-auth-state", "data", allow_duplicate=True),
    Output("modal-auth", "opened", allow_duplicate=True),
    Input("btn-register", "n_clicks"),
    State("auth-register-email", "value"),
    State("auth-register-password", "value"),
    prevent_initial_call=True,
)
def handle_register(
    n_clicks: int | None,
    email: str | None,
    password: str | None,
) -> tuple:
    """Register a new user account and update auth store on success.

    Args:
        n_clicks: Click count from the Create Account button.
        email: Email value from the register form input.
        password: Password value from the register form input.

    Returns:
        Tuple of (error_children, auth_store_data, modal_opened).
    """
    if not n_clicks:
        raise PreventUpdate

    try:
        user = register_user(email or "", password or "")
        flask_session["user_id"] = user.id
        return "", build_auth_store_payload(user), False
    except ValueError as exc:
        msg = str(exc)
        # Suppress "already exists" messages to prevent email enumeration.
        # Surface only validation errors (format, length) verbatim.
        if "already exists" in msg:
            msg = "Could not create account. Please try a different email."
        return dmc.Text(msg, c="red", size="sm"), no_update, no_update
    except Exception:
        logger.exception("Unexpected error during register callback")
        return (
            dmc.Text("Registration failed. Please try again.", c="red", size="sm"),
            no_update,
            no_update,
        )


# ── Phase 7: logout ───────────────────────────────────────────────────────────


@callback(
    Output("store-auth-state", "data", allow_duplicate=True),
    Output("url", "pathname"),
    Input("btn-logout", "n_clicks"),
    prevent_initial_call=True,
)
def handle_logout(n_clicks: int | None) -> tuple:
    """Clear Flask session and redirect to the calculator page on logout.

    Args:
        n_clicks: Click count from the Sign Out button.

    Returns:
        Tuple of (unauthenticated_state, redirect_pathname).
    """
    # prevent_initial_call=True: btn-logout is only rendered when authenticated,
    # so this callback must not fire on initial load.
    logout_user()
    return UNAUTHENTICATED_STATE, "/"


# ── Phase 7: navbar auth controls ────────────────────────────────────────────


@callback(
    Output("navbar-auth-controls", "children"),
    Input("store-auth-state", "data"),
)
def update_navbar_auth_controls(auth_state: dict | None) -> dmc.Button | dmc.Group:
    """Rebuild the navbar auth section whenever auth state changes.

    Renders a Sign In button when unauthenticated, or the user's email
    plus navigation and sign-out buttons when authenticated.

    Args:
        auth_state: The current auth store payload dict.

    Returns:
        A single dmc.Button (unauthenticated) or dmc.Group (authenticated).
    """
    if auth_state and auth_state.get("authenticated"):
        return dmc.Group(
            [
                dmc.Text(auth_state["email"], size="sm", c="dimmed"),
                dcc.Link(
                    dmc.Button(
                        "My Scenarios",
                        id="btn-nav-dashboard",
                        variant="subtle",
                        size="sm",
                    ),
                    href="/dashboard",
                ),
                dmc.Button(
                    "Sign Out",
                    id="btn-logout",
                    variant="subtle",
                    size="sm",
                    color="red",
                ),
            ]
        )
    # Unauthenticated: single Sign In / Register button that opens the modal.
    return dmc.Button(
        "Sign In / Register",
        id="btn-open-auth",
        variant="light",
        size="sm",
    )
