"""Results summary panel component — Phase 6.

Renders a plain-language summary of FI calculation results: three stat cards
and a contextual dmc.Alert with actionable messaging based on success probability.
"""

from __future__ import annotations

import dash_mantine_components as dmc

from app.engine.calculator import MilestoneResult
from app.engine.monte_carlo import SimulationResult


def _stat_card(label: str, value: str, color: str) -> dmc.Paper:
    """Build a single stat card.

    Args:
        label: Short descriptive label shown above the value.
        value: Formatted string value (dollar amount, percentage, etc.).
        color: Mantine color token for the value text.

    Returns:
        A dmc.Paper containing the label and value.
    """
    return dmc.Paper(
        p="md",
        withBorder=True,
        style={"flex": "1"},
        children=[
            dmc.Text(label, size="xs", c="dimmed", mb=4),
            dmc.Text(value, size="xl", fw=700, c=color),
        ],
    )


def get_results_summary(
    result: MilestoneResult,
    sim_result: SimulationResult,
) -> dmc.Paper:
    """Build the results summary panel with stat cards and a contextual alert.

    Args:
        result: MilestoneResult from calculate_all_milestones().
        sim_result: SimulationResult from run_simulation().

    Returns:
        A dmc.Paper containing three stat cards and a plain-language alert.
    """
    rate = sim_result.success_rate
    retirement_age = result.years_to_retirement  # years, not age

    # Success probability color
    if rate >= 0.75:
        prob_color = "green"
    elif rate >= 0.50:
        prob_color = "yellow"
    else:
        prob_color = "red"

    # Contextual alert messaging
    if rate >= 0.85:
        alert_color = "green"
        alert_title = "Looking strong"
        alert_msg = (
            f"At your current savings rate, you have a {rate:.0%} probability "
            f"of reaching your FI number by your target retirement age."
        )
    elif rate >= 0.50:
        alert_color = "yellow"
        alert_title = "On track, with room to improve"
        alert_msg = (
            f"Your plan succeeds in {rate:.0%} of simulations. Consider "
            f"increasing contributions or adjusting your retirement timeline."
        )
    else:
        alert_color = "red"
        alert_title = "Plan needs attention"
        alert_msg = (
            f"Your current plan succeeds in fewer than half of simulations. "
            f"Review your inputs — small changes to contributions or retirement "
            f"age can significantly improve your outlook."
        )

    return dmc.Paper(
        p="md",
        withBorder=True,
        children=[
            dmc.Group(
                gap="sm",
                grow=True,
                mb="md",
                children=[
                    _stat_card(
                        "Coast FI Number",
                        f"${result.coast_fi:,.0f}",
                        "blue",
                    ),
                    _stat_card(
                        "Success Probability",
                        f"{rate:.1%}",
                        prob_color,
                    ),
                    _stat_card(
                        "Years to Retirement",
                        f"{result.years_to_retirement} years",
                        "gray",
                    ),
                ],
            ),
            dmc.Alert(
                children=alert_msg,
                title=alert_title,
                color=alert_color,
            ),
        ],
    )


def get_empty_summary() -> dmc.Paper:
    """Build a placeholder summary panel shown before the first calculation.

    Returns:
        A dmc.Paper with a centered placeholder message.
    """
    return dmc.Paper(
        p="md",
        withBorder=True,
        children=[
            dmc.Text(
                "Your results will appear here.",
                c="dimmed",
                ta="center",
                py="xl",
            )
        ],
    )
