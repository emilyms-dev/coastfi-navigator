"""Share page — Phase 5 placeholder.

Read-only view of a shared scenario identified by URL token. Full
implementation in Phase 7.
"""

import dash
import dash_mantine_components as dmc

dash.register_page(
    __name__,
    path="/share/<token>",
    name="Shared Scenario",
    title="Shared Plan — Coast FI Navigator",
)


def layout(token: str | None = None) -> dmc.Container:
    """Dynamic layout function — required for path parameters in Dash pages.

    Args:
        token: The share token extracted from the URL path. Phase 7 builds
            the real implementation; this stub renders the token for routing
            verification.

    Returns:
        A Container with a placeholder message.
    """
    return dmc.Container(
        [
            dmc.Title("Shared Scenario", order=2, mb="md"),
            dmc.Text(f"Token: {token}", c="dimmed"),
            dmc.Paper(
                children=[dmc.Text("Shared view — Phase 7", c="dimmed")],
                p="xl",
                withBorder=True,
            ),
        ],
        size="lg",
    )
