"""Share page — Phase 7.

Read-only view of a shared scenario. Identified by a UUID token in the URL
path. No input panel, no save button. Watermarked with a "Shared View" badge.

The layout function queries the database directly (via crud) at render time —
appropriate here because the page is fully static once loaded (no interactive
recalculation). The token itself serves as the authorization credential.
"""

from __future__ import annotations

import dash
import dash_mantine_components as dmc
from dash import dcc

from app.components.charts import build_empty_fan_chart, build_fan_chart
from app.components.milestones import get_milestone_cards
from app.components.summary import get_results_summary
from app.db import crud
from app.engine.calculator import (
    calculate_all_milestones,
    calculate_deterministic_projection,
)

dash.register_page(
    __name__,
    path="/share/<token>",
    name="Shared Scenario",
    title="Shared Plan — Coast FI Navigator",
)


def layout(token: str | None = None) -> dmc.Container:
    """Render the read-only shared scenario view.

    Looks up the scenario by share token, deserializes the latest snapshot,
    and renders the full results panel without any input controls.

    Args:
        token: UUID share token extracted from the URL path. None if the
            path was matched without a token (should not happen in practice).

    Returns:
        A dmc.Container with either an error message or the full read-only
        results panel.
    """
    if not token:
        return dmc.Container(
            dmc.Alert("Invalid share link.", color="red"),
            size="lg",
            pt="md",
        )

    scenario = crud.get_scenario_by_share_token(token)
    if not scenario:
        return dmc.Container(
            dmc.Alert(
                "This share link is invalid or has expired.",
                color="red",
            ),
            size="lg",
            pt="md",
        )

    # snapshots are eagerly loaded by get_scenario_by_share_token.
    snapshot = scenario.snapshots[-1] if scenario.snapshots else None
    if not snapshot:
        return dmc.Container(
            dmc.Alert("This scenario has no saved data.", color="gray"),
            size="lg",
            pt="md",
        )

    inputs = crud.deserialize_inputs(snapshot.inputs_json)
    milestones = calculate_all_milestones(inputs)

    sim_result = None
    if snapshot.results_json:
        sim_result = crud.deserialize_results(snapshot.results_json)

    return dmc.Container(
        [
            # ── Header ───────────────────────────────────────────────────────
            dmc.Group(
                justify="space-between",
                mb="xl",
                children=[
                    dmc.Stack(
                        gap=0,
                        children=[
                            dmc.Title(scenario.name, order=2),
                            dmc.Text(
                                "Shared read-only view",
                                size="sm",
                                c="dimmed",
                            ),
                        ],
                    ),
                    dmc.Badge(
                        "Shared View",
                        color="gray",
                        variant="filled",
                        size="lg",
                    ),
                ],
            ),
            # ── Results (read-only, no input panel) ──────────────────────────
            (
                get_results_summary(milestones, sim_result)
                if sim_result
                else dmc.Alert("No simulation data available.", color="gray")
            ),
            dmc.Space(h=16),
            dcc.Graph(
                figure=(
                    build_fan_chart(
                        result=sim_result,
                        deterministic=calculate_deterministic_projection(inputs),
                        fi_number=milestones.traditional_fi,
                    )
                    if sim_result
                    else build_empty_fan_chart()
                ),
                config={"displayModeBar": False},
                style={"height": "420px"},
            ),
            dmc.Space(h=16),
            get_milestone_cards(milestones, inputs.current_portfolio),
            dmc.Space(h="xl"),
            # ── CTA for unauthenticated visitors ─────────────────────────────
            dmc.Paper(
                [
                    dmc.Text(
                        "Want to build your own Coast FI plan?",
                        fw=500,
                        mb="xs",
                    ),
                    dcc.Link(
                        dmc.Button("Get Started", variant="light"),
                        href="/",
                    ),
                ],
                p="md",
                withBorder=True,
            ),
        ],
        size="xl",
        pt="md",
    )
