"""Dashboard page — Phase 7.

Displays saved scenarios for the authenticated user. The scenario list is
populated by the load_dashboard_scenarios callback in callbacks/persistence.py
whenever the user navigates to this page.
"""

import dash
import dash_mantine_components as dmc
from dash import dcc, html

dash.register_page(
    __name__,
    path="/dashboard",
    name="Dashboard",
    title="My Scenarios — Coast FI Navigator",
)

layout = dmc.Container(
    [
        dmc.Group(
            justify="space-between",
            mb="xl",
            children=[
                dmc.Title("My Scenarios", order=2),
                dcc.Link(
                    dmc.Button("+ New Plan", variant="light"),
                    href="/",
                ),
            ],
        ),
        # Populated by load_dashboard_scenarios callback on navigation.
        # Skeletons shown as placeholders before the callback fires.
        html.Div(
            id="dashboard-scenario-list",
            children=[dmc.Skeleton(height=120, mb="sm") for _ in range(3)],
        ),
    ],
    size="lg",
    pt="md",
)
