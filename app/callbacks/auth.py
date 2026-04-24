"""Auth state callbacks — Phase 5.

Syncs Flask session auth state into the Dash store on every page navigation,
ensuring the client-side store never goes stale after session expiry or logout.
"""

from dash import Input, Output, callback

from app.auth.users import (
    UNAUTHENTICATED_STATE,
    build_auth_store_payload,
    get_current_user,
)


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
