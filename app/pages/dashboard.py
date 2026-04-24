"""Dashboard page — Phase 5 placeholder.

Displays saved scenarios for the authenticated user. Full implementation
in Phase 7.
"""

import dash
import dash_mantine_components as dmc

dash.register_page(
    __name__,
    path="/dashboard",
    name="Dashboard",
    title="My Scenarios — Coast FI Navigator",
)

layout = dmc.Container(
    [
        dmc.Title("My Scenarios", order=2, mb="md"),
        dmc.Paper(
            children=[dmc.Text("Saved scenarios — Phase 7", c="dimmed")],
            p="xl",
            withBorder=True,
        ),
    ],
    size="lg",
)
