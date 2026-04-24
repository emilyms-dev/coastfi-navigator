"""Milestone progress display components — Phase 6.

Renders FI milestone progress bars from a MilestoneResult. Progress colors
always come from milestones.get_progress_color() — never hardcoded.
"""

from __future__ import annotations

import dash_mantine_components as dmc

from app.engine.calculator import MilestoneResult
from app.engine.milestones import MILESTONE_DEFINITIONS, get_progress_color


def get_milestone_cards(
    result: MilestoneResult,
    current_portfolio: float,
) -> dmc.Stack:
    """Build milestone progress cards from a completed calculation result.

    Args:
        result: MilestoneResult from calculate_all_milestones().
        current_portfolio: Current portfolio value in USD, used to derive
            progress percentages.

    Returns:
        A dmc.Stack of dmc.Paper cards — one per milestone, in display order.
    """
    cards = []
    for milestone in sorted(MILESTONE_DEFINITIONS, key=lambda m: m["order"]):
        key = milestone["key"]
        label = milestone["label"]
        milestone_value: float = getattr(result, f"{key}_fi")

        # Progress is capped at 100 to keep the bar visually bounded.
        pct = min(current_portfolio / milestone_value * 100.0, 100.0) if milestone_value > 0 else 0.0
        color = get_progress_color(pct)

        cards.append(
            dmc.Paper(
                p="md",
                withBorder=True,
                children=[
                    dmc.Group(
                        justify="space-between",
                        mb=4,
                        children=[
                            dmc.Text(label, fw=500),
                            dmc.Badge(
                                f"${milestone_value:,.0f}",
                                color=color,
                                variant="light",
                            ),
                        ],
                    ),
                    dmc.Progress(
                        value=pct,
                        color=color,
                        size="md",
                        radius="xl",
                        mb=4,
                    ),
                    dmc.Text(
                        f"{pct:.1f}% of the way there",
                        size="xs",
                        c="dimmed",
                    ),
                ],
            )
        )

    return dmc.Stack(cards, gap="xs")


def get_empty_milestone_cards() -> dmc.Stack:
    """Build placeholder skeleton cards shown before the first calculation.

    Returns:
        A dmc.Stack of 5 dmc.Skeleton components.
    """
    return dmc.Stack(
        [dmc.Skeleton(height=80, radius="md") for _ in range(5)],
        gap="xs",
    )
