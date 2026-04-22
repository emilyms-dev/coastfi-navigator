"""Top-level Dash layout assembly.

Defines the MantineProvider theme, the application shell (navbar + page
container), and all dcc.Store components used for client-side state.
No callbacks are defined here — see app/callbacks/ for all callback logic.
"""

import dash
import dash_mantine_components as dmc
from dash import dcc

# ── Theme ─────────────────────────────────────────────────────────────────────
# Defined once here and passed to MantineProvider — never inline color hex codes.

THEME = {
    "primaryColor": "blue",
    "fontFamily": (
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
        "Helvetica, Arial, sans-serif"
    ),
}

# ── Navbar ────────────────────────────────────────────────────────────────────


def _build_header() -> dmc.AppShellHeader:
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
                    dmc.Stack(
                        gap=0,
                        children=[
                            dmc.Title("Coast FI Navigator", order=3),
                            dmc.Text(
                                "Probabilistic financial independence planning",
                                size="sm",
                                c="dimmed",
                            ),
                        ],
                    ),
                    # Placeholder for auth buttons — populated in Phase 4
                    dmc.Group(id="navbar-auth-controls"),
                ],
            )
        ],
    )


# ── Layout factory ────────────────────────────────────────────────────────────


def build_layout() -> dmc.MantineProvider:
    """Construct and return the root application layout.

    Called once at startup in app/main.py. All dcc.Store components that
    persist client-side state must be declared here.

    Returns:
        The fully assembled MantineProvider layout tree.
    """
    return dmc.MantineProvider(
        theme=THEME,
        children=[
            dmc.AppShell(
                header={"height": 64},
                padding="md",
                children=[
                    _build_header(),
                    dmc.AppShellMain(
                        children=[
                            # ── Client-side state stores ───────────────
                            # Calculator input values — persisted across page navigation
                            dcc.Store(
                                id="store-user-inputs",
                                storage_type="session",
                            ),
                            # Holds most recent Monte Carlo output — cleared on refresh
                            dcc.Store(
                                id="store-simulation-results",
                                storage_type="memory",
                            ),
                            # ID of the currently loaded saved scenario, if any
                            dcc.Store(
                                id="store-active-scenario-id",
                                storage_type="session",
                            ),
                            # Auth state: {authenticated: bool, user_id: int|null}
                            dcc.Store(
                                id="store-auth-state",
                                storage_type="session",
                            ),
                            # ── Page container ────────────────────────
                            dmc.Container(
                                size="xl",
                                pt="md",
                                pb="xl",
                                children=[dash.page_container],
                            ),
                        ]
                    ),
                ],
            )
        ],
    )
