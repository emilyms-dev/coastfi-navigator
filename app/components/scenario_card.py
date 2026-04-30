"""Scenario card component — Phase 7.

Renders a single saved scenario as a dmc.Paper card with a preview of the
saved inputs, the version badge, and Load / Share / Delete action buttons.
Used on the dashboard to list all of a user's saved scenarios.
"""

from __future__ import annotations

import dash_mantine_components as dmc

from app.db.crud import deserialize_inputs
from app.db.models import Scenario, ScenarioSnapshot


def get_scenario_card(
    scenario: Scenario,
    latest_snapshot: ScenarioSnapshot | None,
) -> dmc.Paper:
    """Build a scenario preview card.

    Args:
        scenario: The Scenario ORM object (detached, attributes already loaded).
        latest_snapshot: The most recent ScenarioSnapshot for this scenario,
            or None if the scenario has never been saved.

    Returns:
        A dmc.Paper card with metadata preview and action buttons.
    """
    snapshot_date = (
        latest_snapshot.created_at.strftime("%b %d, %Y")
        if latest_snapshot
        else "No saves yet"
    )

    # Build a one-line summary from the stored inputs if available.
    preview_text = "No data"
    if latest_snapshot and latest_snapshot.inputs_json:
        inputs = deserialize_inputs(latest_snapshot.inputs_json)
        preview_text = (
            f"Age {inputs.current_age} → {inputs.retirement_age} · "
            f"${inputs.annual_spending:,.0f}/yr · "
            f"v{latest_snapshot.version}"
        )

    return dmc.Paper(
        children=[
            dmc.Group(
                justify="space-between",
                mb="xs",
                children=[
                    dmc.Text(scenario.name, fw=600, size="md"),
                    dmc.Badge(
                        f"v{latest_snapshot.version}" if latest_snapshot else "Empty",
                        variant="light",
                    ),
                ],
            ),
            dmc.Text(preview_text, size="sm", c="dimmed", mb="sm"),
            dmc.Text(f"Saved {snapshot_date}", size="xs", c="dimmed", mb="md"),
            dmc.Group(
                children=[
                    dmc.Button(
                        "Load",
                        id={"type": "btn-load-scenario", "index": scenario.id},
                        size="xs",
                        variant="light",
                    ),
                    dmc.Button(
                        "Share",
                        id={"type": "btn-share-scenario", "index": scenario.id},
                        size="xs",
                        variant="subtle",
                    ),
                    dmc.Button(
                        "Delete",
                        id={"type": "btn-delete-scenario", "index": scenario.id},
                        size="xs",
                        variant="subtle",
                        color="red",
                    ),
                ]
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )
