"""Calculation callbacks — Phase 6.

Two callbacks drive the debounce-then-calculate pattern:

1. arm_debounce  — gates the debounce interval. Fires on any input change
   and enables the dcc.Interval, resetting its counter to 0 so the 400ms
   clock starts fresh from the moment of the last keystroke.

2. run_calculation — fires 400ms after the interval is enabled, performs
   the full engine call chain, and immediately disables the interval so it
   does not repeat every 400ms.

Both callbacks are registered with Dash's global callback registry via
``@callback``; no reference to the Dash app instance is required here.
"""

from __future__ import annotations

import json
import logging

import dash
import dash
from dash import Input, Output, State, callback

from app.components.charts import build_fan_chart
from app.components.milestones import get_milestone_cards
from app.components.summary import get_results_summary
from app.engine.calculator import FIInputs, calculate_all_milestones, calculate_deterministic_projection
from app.engine.monte_carlo import run_simulation

logger = logging.getLogger(__name__)

# ── Input IDs ─────────────────────────────────────────────────────────────────

_INPUT_IDS: list[str] = [
    "input-current-age",
    "input-retirement-age",
    "input-current-portfolio",
    "input-monthly-contribution",
    "input-annual-spending",
    "input-nominal-return",
    "input-inflation-rate",
    "input-barista-income",
]


# ── Callback 1: Debounce gate ─────────────────────────────────────────────────


@callback(
    Output("calc-debounce-trigger", "disabled"),
    Output("calc-debounce-trigger", "n_intervals"),
    [Input(id_, "value") for id_ in _INPUT_IDS],
    prevent_initial_call=True,
)
def arm_debounce(*_values: object) -> tuple[bool, int]:
    """Enable the debounce interval whenever any input value changes.

    Resets n_intervals to 0 so the 400ms window starts from the moment of
    the most recent keystroke, not from the moment the interval was first
    enabled.

    Args:
        *_values: Current values of all numeric inputs (unused — only the
            fact that a change occurred matters here).

    Returns:
        Tuple of (disabled=False, n_intervals=0) to arm the interval.
    """
    return False, 0


# ── Callback 2: Main calculation ──────────────────────────────────────────────


@callback(
    Output("calc-fan-chart", "figure"),
    Output("calc-summary-container", "children"),
    Output("calc-milestone-container", "children"),
    Output("store-simulation-results", "data"),
    Output("store-user-inputs", "data"),
    Output("calc-debounce-trigger", "disabled", allow_duplicate=True),
    Input("calc-debounce-trigger", "n_intervals"),
    [State(id_, "value") for id_ in _INPUT_IDS],
    prevent_initial_call=True,
)
def run_calculation(
    n_intervals: int,
    current_age: object,
    retirement_age: object,
    current_portfolio: object,
    monthly_contribution: object,
    annual_spending: object,
    nominal_return_pct: object,
    inflation_rate_pct: object,
    barista_income: object,
) -> tuple:
    """Execute the full FI calculation and update all result components.

    Fires 400ms after the debounce interval is enabled. Immediately
    disables the interval on exit so it does not fire again every 400ms.

    Percentage inputs (nominal_return_pct, inflation_rate_pct) are stored
    as percentages in the UI (7.0 means 7%) and converted to decimals
    (0.07) before being passed to the engine.

    Args:
        n_intervals: Interval fire counter (unused value; presence of the
            Input is sufficient to trigger the callback).
        current_age: Current age in whole years.
        retirement_age: Target retirement age in whole years.
        current_portfolio: Current portfolio value in USD.
        monthly_contribution: Monthly contribution in USD.
        annual_spending: Expected annual spending in retirement, USD.
        nominal_return_pct: Expected annual nominal return as a percentage
            (e.g. 7.0 for 7%).
        inflation_rate_pct: Expected annual inflation as a percentage
            (e.g. 3.0 for 3%).
        barista_income: Annual part-time income in USD (may be 0).

    Returns:
        Tuple of:
            - go.Figure  — updated fan chart
            - list       — summary container children
            - list       — milestone container children
            - str | None — serialised SimulationResult for store (JSON)
            - str | None — serialised inputs for store (JSON)
            - bool       — calc-debounce-trigger disabled=True
    """
    # Always disable interval so it doesn't repeat every 400ms.
    _interval_disabled = True

    # ── 1. Validate inputs ────────────────────────────────────────────────────
    raw_inputs = [
        current_age,
        retirement_age,
        current_portfolio,
        monthly_contribution,
        annual_spending,
        nominal_return_pct,
        inflation_rate_pct,
        barista_income,
    ]
    # _no_update_with_disable: returned on any validation/engine failure.
    # UI outputs are left unchanged; interval is disabled so it stops firing.
    _no_update_with_disable = (
        dash.no_update,  # calc-fan-chart figure
        dash.no_update,  # calc-summary-container children
        dash.no_update,  # calc-milestone-container children
        dash.no_update,  # store-simulation-results data
        dash.no_update,  # store-user-inputs data
        True,            # calc-debounce-trigger disabled — stop the interval
    )

    if any(v is None for v in raw_inputs):
        return _no_update_with_disable

    try:
        fi_inputs = FIInputs(
            current_age=int(current_age),
            retirement_age=int(retirement_age),
            current_portfolio=float(current_portfolio),
            monthly_contribution=float(monthly_contribution),
            annual_spending=float(annual_spending),
            # Percentage inputs arrive as percent (7.0) → convert to decimal (0.07)
            nominal_return_rate=float(nominal_return_pct) / 100.0,
            inflation_rate=float(inflation_rate_pct) / 100.0,
            barista_income=float(barista_income),
        )
    except (TypeError, ValueError) as exc:
        logger.warning("Input coercion failed: %s", exc)
        return _no_update_with_disable

    # ── 2. Engine calls ───────────────────────────────────────────────────────
    try:
        milestone_result = calculate_all_milestones(fi_inputs)
        sim_result = run_simulation(fi_inputs)
        deterministic = calculate_deterministic_projection(fi_inputs)
    except ValueError as exc:
        logger.warning("Calculation validation error: %s", exc)
        return _no_update_with_disable
    except Exception:
        logger.exception("Unexpected error during FI calculation")
        return _no_update_with_disable

    # ── 3. Build UI components ────────────────────────────────────────────────
    figure = build_fan_chart(
        result=sim_result,
        deterministic=deterministic,
        fi_number=milestone_result.traditional_fi,
    )
    summary_children = [get_results_summary(milestone_result, sim_result)]
    milestone_children = [
        get_milestone_cards(milestone_result, float(current_portfolio))
    ]

    # ── 4. Serialise for dcc.Store ────────────────────────────────────────────
    sim_store = json.dumps(
        {
            "success_rate": sim_result.success_rate,
            "n_simulations": sim_result.n_simulations,
            "fi_number": sim_result.fi_number,
            "inputs_snapshot": sim_result.inputs_snapshot,
        }
    )
    inputs_store = json.dumps(
        {
            "current_age": fi_inputs.current_age,
            "retirement_age": fi_inputs.retirement_age,
            "current_portfolio": fi_inputs.current_portfolio,
            "monthly_contribution": fi_inputs.monthly_contribution,
            "annual_spending": fi_inputs.annual_spending,
            "nominal_return_rate": fi_inputs.nominal_return_rate,
            "inflation_rate": fi_inputs.inflation_rate,
            "barista_income": fi_inputs.barista_income,
        }
    )

    return (
        figure,
        summary_children,
        milestone_children,
        sim_store,
        inputs_store,
        _interval_disabled,
    )
