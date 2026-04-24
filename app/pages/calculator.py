"""Calculator page — Phase 5 placeholder.

Full implementation in Phase 6. This stub verifies routing and the
AppShell layout work correctly before calculator logic is wired in.
"""

import dash
import dash_mantine_components as dmc

dash.register_page(
    __name__,
    path="/",
    name="Calculator",
    title="Coast FI Navigator",
)

layout = dmc.Container(
    [
        dmc.Title("Coast FI Calculator", order=2, mb="md"),
        dmc.Text(
            "Enter your details below to calculate your Coast FI number.",
            c="dimmed",
            mb="xl",
        ),
        dmc.Paper(
            children=[dmc.Text("Calculator inputs — Phase 6", c="dimmed")],
            p="xl",
            withBorder=True,
        ),
    ],
    size="lg",
)
