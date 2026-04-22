"""FI milestone definitions and display metadata — Phase 2.

This module is the UI layer's single source of truth for milestone keys,
labels, descriptions, and color tokens. It deliberately does not import from
``calculator.py`` so that display logic and math logic remain decoupled: the
UI imports ``milestones.py`` for metadata and ``calculator.py`` for numbers.
"""

from __future__ import annotations

MILESTONE_DEFINITIONS: list[dict] = [
    {
        "key": "lean",
        "label": "Lean FI",
        "description": "Cover a minimal lifestyle. No frills, full freedom.",
        "multiplier": 20.0,
        "color": "teal",
        "order": 1,
    },
    {
        "key": "coast",
        "label": "Coast FI",
        "description": ("Let compound growth do the rest. Stop contributing today."),
        "multiplier": None,
        "color": "blue",
        "order": 2,
    },
    {
        "key": "barista",
        "label": "Barista FI",
        "description": (
            "Part-time work covers the gap. Your portfolio covers the rest."
        ),
        "multiplier": None,
        "color": "violet",
        "order": 3,
    },
    {
        "key": "traditional",
        "label": "Traditional FI",
        "description": "Full financial independence at the 4% withdrawal rate.",
        "multiplier": 25.0,
        "color": "green",
        "order": 4,
    },
    {
        "key": "fat",
        "label": "Fat FI",
        "description": "Generously funded retirement with significant buffer.",
        "multiplier": 33.0,
        "color": "grape",
        "order": 5,
    },
]


def get_milestone_meta(key: str) -> dict:
    """Retrieve the metadata dict for a milestone by its key.

    Args:
        key: Milestone key ("lean", "coast", "barista", "traditional", "fat").

    Returns:
        The metadata dict for the requested milestone.

    Raises:
        KeyError: If ``key`` does not match any defined milestone.
    """
    for entry in MILESTONE_DEFINITIONS:
        if entry["key"] == key:
            return entry
    raise KeyError(f"Unknown milestone key: {key!r}")


def get_progress_color(progress_pct: float) -> str:
    """Return a Mantine color token for a progress percentage.

    The bands are intentionally chosen so that the color shifts from red to
    green as the user approaches and then meets a milestone.

    Args:
        progress_pct: Progress toward a milestone as a percentage (0–100+).

    Returns:
        A Mantine color token: ``"red"`` for 0–40, ``"yellow"`` for 40–80,
        ``"lime"`` for 80–100, ``"green"`` for values >= 100.
    """
    if progress_pct >= 100.0:
        return "green"
    if progress_pct >= 80.0:
        return "lime"
    if progress_pct >= 40.0:
        return "yellow"
    return "red"
