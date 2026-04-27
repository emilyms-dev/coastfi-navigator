"""Top-level Dash layout assembly.

Defines the MantineProvider theme, the application shell (navbar + page
container), and all dcc.Store components used for client-side state.
No callbacks are defined here — see app/callbacks/ for all callback logic.
"""

import dash
import dash_mantine_components as dmc
from dash import dcc

from app.auth.users import UNAUTHENTICATED_STATE
from app.components.auth_modal import get_auth_modal

# ── Theme ─────────────────────────────────────────────────────────────────────
# Defined once here and passed to MantineProvider — never inline color hex codes.

THEME = {
    # "colorScheme" is a Mantine v6 key ignored by v7/DMC 2.x.
    # Use forceColorScheme="light" on MantineProvider if locking color mode.
    "primaryColor": "blue",
    "fontFamily": "'Inter', 'Segoe UI', sans-serif",
    "defaultRadius": "md",
    "components": {
        "Button": {"defaultProps": {"radius": "md"}},
        "Paper": {"defaultProps": {"radius": "md", "shadow": "sm"}},
    },
}

# ── Navbar ────────────────────────────────────────────────────────────────────


def get_navbar() -> dmc.AppShellHeader:
    """Build the top application header.

    Returns:
        A dmc.AppShellHeader containing the app title, tagline,
        and a placeholder for auth controls.
    """
    return dmc.AppShellHeader(
        p="md",
        children=[
            dmc.Group(
                justify="space-between",
                align="center",
                h="100%",
                children=[
                    dmc.Group(
                        children=[
                            dmc.Title("Coast FI Navigator", order=3, c="blue"),
                            dmc.Text(
                                "Your path to financial freedom",
                                size="xs",
                                c="dimmed",
                                visibleFrom="sm",
                            ),
                        ]
                    ),
                    # Auth controls populated by Phase 7 callback
                    dmc.Group(id="navbar-auth-controls", children=[]),
                ],
            )
        ],
    )


# ── Layout factory ────────────────────────────────────────────────────────────


def get_layout() -> dmc.MantineProvider:
    """Construct and return the root application layout.

    Called once at startup in app/main.py. All dcc.Store components that
    persist client-side state must be declared here.

    Returns:
        The fully assembled MantineProvider layout tree.
    """
    return dmc.MantineProvider(
        theme=THEME,
        forceColorScheme="light",
        children=[
            # NotificationProvider enables dmc.Notification(action="show")
            # to render as real toasts rather than static inline blocks.
            dmc.NotificationProvider(position="top-right"),
            dmc.AppShell(
                header={"height": 60},
                padding="md",
                children=[
                    get_navbar(),
                    dmc.AppShellMain(
                        children=[
                            dmc.Container(
                                children=[dash.page_container],
                                size="lg",
                                pt="xl",
                                pb="xl",
                            ),
                            # ── Client-side state stores ──────────────────
                            dcc.Store(
                                id="store-user-inputs",
                                storage_type="session",
                            ),
                            # Persists calculator inputs across page navigation.
                            dcc.Store(
                                id="store-simulation-results",
                                storage_type="memory",
                            ),
                            # Latest Monte Carlo output. Cleared on refresh.
                            dcc.Store(
                                id="store-active-scenario-id",
                                storage_type="session",
                            ),
                            # Currently loaded scenario ID, None if unsaved.
                            dcc.Store(
                                id="store-auth-state",
                                storage_type="session",
                                data=UNAUTHENTICATED_STATE,
                            ),
                            # Flask session auth state. Synced by auth callback.
                            dcc.Location(id="url", refresh=False),
                            # Required for programmatic navigation in callbacks.
                            # ── Auth modal ────────────────────────────────────
                            # Must live at the root level so it overlays every page.
                            get_auth_modal(),
                            # ── Notification target ───────────────────────────
                            # Persistence and auth callbacks write dmc.Notification
                            # objects here. Fixed position keeps them visible above
                            # page content without disrupting layout flow.
                            dmc.Box(
                                id="notifications-container",
                                style={
                                    "position": "fixed",
                                    "top": "80px",
                                    "right": "16px",
                                    "zIndex": 9999,
                                    "width": "320px",
                                },
                            ),
                        ]
                    ),
                ],
            )
        ],
    )
