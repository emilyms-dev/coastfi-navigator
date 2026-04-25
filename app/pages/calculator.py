"""Calculator page — Phase 6.

Main user-facing page. Renders the input panel on the left and the results
panel (summary, fan chart, milestone bars) on the right. All recalculation
logic lives in app/callbacks/calculation.py — this file is callback-free.
"""

import dash
import dash_mantine_components as dmc
from dash import dcc, html

from app.components.charts import build_empty_fan_chart
from app.components.inputs import get_input_panel
from app.components.milestones import get_empty_milestone_cards
from app.components.summary import get_empty_summary

dash.register_page(
    __name__,
    path="/",
    name="Calculator",
    title="Coast FI Navigator",
)

layout = dmc.Container(
    [
        # ── Page header ───────────────────────────────────────────────────────
        dmc.Title("Coast FI Calculator", order=2, mb=4),
        dmc.Text(
            "How much do you need invested today to retire "
            "without contributing another dollar?",
            c="dimmed",
            mb="xl",
        ),
        dmc.Grid(
            [
                # ── Left column: inputs ───────────────────────────────────────
                dmc.GridCol(
                    [get_input_panel()],
                    span={"base": 12, "md": 4},
                ),
                # ── Right column: outputs ─────────────────────────────────────
                dmc.GridCol(
                    [
                        # Results summary: stat cards + contextual alert
                        html.Div(
                            id="calc-summary-container",
                            children=[get_empty_summary()],
                        ),
                        dmc.Space(h=16),
                        # Fan chart — primary visual, must stay above the fold
                        dcc.Graph(
                            id="calc-fan-chart",
                            figure=build_empty_fan_chart(),
                            config={"displayModeBar": False},
                            style={"height": "420px"},
                        ),
                        dmc.Space(h=16),
                        # Milestone progress bars
                        html.Div(
                            id="calc-milestone-container",
                            children=[get_empty_milestone_cards()],
                        ),
                    ],
                    span={"base": 12, "md": 8},
                ),
            ],
            gutter="xl",
        ),
        # Debounce trigger — arms on any input change, fires 400ms later.
        # The gate callback enables it; the main calculation callback disables
        # it after firing so it does not repeat every 400ms.
        dcc.Interval(
            id="calc-debounce-trigger",
            interval=400,
            n_intervals=0,
            disabled=True,
        ),
    ],
    size="xl",
    pt="md",
)
