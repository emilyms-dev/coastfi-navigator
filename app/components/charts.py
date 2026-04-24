"""Plotly chart builders — Phase 6.

Pure functions that construct go.Figure objects from engine output.
No Dash components are defined here — only figure factories.
All formatting of dollar amounts happens via Plotly axis config, not in the
engine layer.
"""

from __future__ import annotations

import plotly.graph_objects as go

from app.engine.monte_carlo import SimulationResult

_CHART_LAYOUT = dict(
    xaxis_title="Age",
    yaxis_title="Portfolio Value",
    yaxis=dict(tickprefix="$", tickformat=",.0f"),
    legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
    hovermode="x unified",
    template="plotly_white",
    margin=dict(t=40, b=40, l=60, r=20),
)


def build_fan_chart(
    result: SimulationResult,
    deterministic: list[tuple[int, float]],
    fi_number: float,
) -> go.Figure:
    """Build the Monte Carlo fan chart with percentile bands.

    Layers (bottom to top):
      1. 10th–90th percentile filled band (wide, faint)
      2. 25th–75th percentile filled band (narrow, stronger)
      3. 50th percentile median line
      4. Deterministic fixed-rate projection (dashed gray)
      5. Horizontal FI target line (dashed green)

    Args:
        result: SimulationResult from run_simulation().
        deterministic: List of (age, portfolio_value) tuples from
            calculate_deterministic_projection().
        fi_number: The Traditional FI target in USD, used for the target line.

    Returns:
        A fully configured go.Figure.
    """
    ages = result.ages
    bands = result.percentile_bands
    fig = go.Figure()

    # ── 10th–90th band (wide, faint fill) ───────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=bands[10],
            fill=None,
            mode="lines",
            line=dict(color="rgba(59,130,246,0)"),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=bands[90],
            fill="tonexty",
            mode="lines",
            line=dict(color="rgba(59,130,246,0)"),
            fillcolor="rgba(59,130,246,0.12)",
            name="10th–90th percentile",
            hoverinfo="skip",
        )
    )

    # ── 25th–75th band (narrower, stronger fill) ─────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=bands[25],
            fill=None,
            mode="lines",
            line=dict(color="rgba(59,130,246,0)"),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=bands[75],
            fill="tonexty",
            mode="lines",
            line=dict(color="rgba(59,130,246,0)"),
            fillcolor="rgba(59,130,246,0.25)",
            name="25th–75th percentile",
            hoverinfo="skip",
        )
    )

    # ── Median projection ────────────────────────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=bands[50],
            mode="lines",
            line=dict(color="rgb(59,130,246)", width=2),
            name="Median projection",
        )
    )

    # ── Deterministic fixed-rate projection ──────────────────────────────────
    det_ages = [pt[0] for pt in deterministic]
    det_values = [pt[1] for pt in deterministic]
    fig.add_trace(
        go.Scatter(
            x=det_ages,
            y=det_values,
            mode="lines",
            line=dict(color="gray", dash="dash", width=1.5),
            name="Fixed-rate projection",
        )
    )

    # ── FI target horizontal line ────────────────────────────────────────────
    fig.add_hline(
        y=fi_number,
        line_dash="dash",
        line_color="green",
        annotation_text="FI Target",
        annotation_position="right",
    )

    fig.update_layout(title="Portfolio Projection", **_CHART_LAYOUT)
    return fig


def build_empty_fan_chart() -> go.Figure:
    """Build a blank placeholder chart shown before the first calculation.

    Returns:
        A go.Figure with a centered annotation prompting the user to enter
        their details. No data traces.
    """
    fig = go.Figure()
    fig.add_annotation(
        text="Enter your details to see your projection.",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color="gray"),
    )
    fig.update_layout(title="Portfolio Projection", **_CHART_LAYOUT)
    # Hide axes on the placeholder — done via dedicated helpers to avoid
    # conflict with the xaxis/yaxis keys already present in _CHART_LAYOUT.
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig
