"""Auth modal component — Phase 7.

A single reusable modal that contains both the login and register forms in
dmc.Tabs. The modal is always present in the root layout (mounted at the top
level so it can overlay every page) and is opened/closed by auth callbacks.
"""

from __future__ import annotations

import dash_mantine_components as dmc


def get_auth_modal() -> dmc.Modal:
    """Build the login/register modal.

    The modal starts closed (opened=False). The open_auth_modal callback
    sets opened=True; handle_login and handle_register set it back to False
    on successful authentication.

    Returns:
        A dmc.Modal containing tabbed login and register forms.
    """
    return dmc.Modal(
        id="modal-auth",
        title="Welcome to Coast FI Navigator",
        centered=True,
        size="sm",
        opened=False,
        children=[
            dmc.Tabs(
                value="login",
                children=[
                    dmc.TabsList(
                        [
                            dmc.TabsTab("Sign In", value="login"),
                            dmc.TabsTab("Register", value="register"),
                        ]
                    ),
                    # ── Login tab ─────────────────────────────────────────────
                    dmc.TabsPanel(
                        value="login",
                        pt="xs",
                        children=[
                            dmc.Stack(
                                gap="xs",
                                mt="md",
                                children=[
                                    dmc.TextInput(
                                        id="auth-login-email",
                                        label="Email",
                                        placeholder="you@example.com",
                                    ),
                                    dmc.PasswordInput(
                                        id="auth-login-password",
                                        label="Password",
                                    ),
                                    dmc.Button(
                                        "Sign In",
                                        id="btn-login",
                                        fullWidth=True,
                                        mt="sm",
                                    ),
                                    # Populated by handle_login callback on error.
                                    dmc.Box(id="auth-login-error"),
                                ],
                            ),
                        ],
                    ),
                    # ── Register tab ──────────────────────────────────────────
                    dmc.TabsPanel(
                        value="register",
                        pt="xs",
                        children=[
                            dmc.Stack(
                                gap="xs",
                                mt="md",
                                children=[
                                    dmc.TextInput(
                                        id="auth-register-email",
                                        label="Email",
                                        placeholder="you@example.com",
                                    ),
                                    dmc.PasswordInput(
                                        id="auth-register-password",
                                        label="Password",
                                        description="Minimum 8 characters",
                                    ),
                                    dmc.Button(
                                        "Create Account",
                                        id="btn-register",
                                        fullWidth=True,
                                        mt="sm",
                                    ),
                                    # Populated by handle_register callback on error.
                                    dmc.Box(id="auth-register-error"),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
