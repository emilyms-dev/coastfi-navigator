"""Simulation tests — Phase 2.

Unit and property-based tests for app/engine/monte_carlo.py.
Verifies success rate bounds, RNG seedability, structured output shape,
and 1,000-run performance budget (< 3 seconds).
"""

from __future__ import annotations

import time

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.engine.calculator import FIInputs
from app.engine.monte_carlo import SimulationResult, run_simulation

KNOWN_INPUTS = FIInputs(
    current_age=30,
    retirement_age=65,
    current_portfolio=150_000.0,
    monthly_contribution=2_000.0,
    annual_spending=60_000.0,
    nominal_return_rate=0.07,
    inflation_rate=0.03,
)


def test_simulation_result_structure() -> None:
    result = run_simulation(KNOWN_INPUTS, n_simulations=1000, rng_seed=0)
    assert isinstance(result, SimulationResult)
    assert set(result.percentile_bands.keys()) == {10, 25, 50, 75, 90}
    expected_len = KNOWN_INPUTS.retirement_age - KNOWN_INPUTS.current_age + 1
    for band in result.percentile_bands.values():
        assert len(band) == expected_len
    assert result.ages[0] == KNOWN_INPUTS.current_age
    assert result.ages[-1] == KNOWN_INPUTS.retirement_age
    assert len(result.ages) == expected_len
    assert 0.0 <= result.success_rate <= 1.0
    assert result.n_simulations == 1000
    assert isinstance(result.inputs_snapshot, dict)
    for expected_key in (
        "current_age",
        "retirement_age",
        "current_portfolio",
        "annual_spending",
        "nominal_return_rate",
        "inflation_rate",
    ):
        assert expected_key in result.inputs_snapshot
    assert result.fi_number == KNOWN_INPUTS.annual_spending * 25.0


def test_seeded_simulation_reproducible() -> None:
    a = run_simulation(KNOWN_INPUTS, n_simulations=500, rng_seed=42)
    b = run_simulation(KNOWN_INPUTS, n_simulations=500, rng_seed=42)
    assert a.percentile_bands.keys() == b.percentile_bands.keys()
    for key in a.percentile_bands:
        assert a.percentile_bands[key] == b.percentile_bands[key]
    assert a.success_rate == b.success_rate


def test_distinct_seeds_produce_different_bands() -> None:
    # Use two distinct fixed seeds rather than rng_seed=None to avoid
    # the vanishingly small but non-zero risk of identical random outputs.
    a = run_simulation(KNOWN_INPUTS, n_simulations=500, rng_seed=1)
    b = run_simulation(KNOWN_INPUTS, n_simulations=500, rng_seed=2)
    assert a.percentile_bands[50] != b.percentile_bands[50]


def test_percentile_ordering() -> None:
    result = run_simulation(KNOWN_INPUTS, n_simulations=1000, rng_seed=7)
    for i in range(len(result.ages)):
        b10 = result.percentile_bands[10][i]
        b25 = result.percentile_bands[25][i]
        b50 = result.percentile_bands[50][i]
        b75 = result.percentile_bands[75][i]
        b90 = result.percentile_bands[90][i]
        assert b10 <= b25 <= b50 <= b75 <= b90


def test_high_return_high_success() -> None:
    generous = FIInputs(
        current_age=25,
        retirement_age=65,
        current_portfolio=200_000.0,
        monthly_contribution=0.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.20,
        inflation_rate=0.03,
    )
    result = run_simulation(generous, n_simulations=1000, rng_seed=3)
    assert result.success_rate > 0.90


def test_zero_portfolio_low_success() -> None:
    inputs = FIInputs(
        current_age=55,
        retirement_age=65,
        current_portfolio=0.0,
        monthly_contribution=0.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.07,
        inflation_rate=0.03,
    )
    result = run_simulation(inputs, n_simulations=1000, rng_seed=5)
    assert result.success_rate < 0.50


def test_simulation_performance() -> None:
    start = time.perf_counter()
    run_simulation(KNOWN_INPUTS, n_simulations=1000)
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0, f"1000-run simulation took {elapsed:.3f}s (limit 3.0s)"


def test_simulation_rejects_zero_runs() -> None:
    with pytest.raises(ValueError, match="n_simulations"):
        run_simulation(KNOWN_INPUTS, n_simulations=0)


def test_simulation_validates_inputs() -> None:
    bad = FIInputs(
        current_age=40,
        retirement_age=35,  # invalid
        current_portfolio=0.0,
        monthly_contribution=0.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.07,
        inflation_rate=0.03,
    )
    with pytest.raises(ValueError, match="retirement_age"):
        run_simulation(bad, n_simulations=10, rng_seed=1)


def test_starting_values_match_current_portfolio() -> None:
    result = run_simulation(KNOWN_INPUTS, n_simulations=200, rng_seed=11)
    for band in result.percentile_bands.values():
        assert band[0] == KNOWN_INPUTS.current_portfolio


# ── Hypothesis property tests ─────────────────────────────────────────


@st.composite
def _valid_inputs(draw) -> FIInputs:
    current_age = draw(st.integers(min_value=18, max_value=60))
    retirement_age = draw(st.integers(min_value=current_age + 1, max_value=80))
    nominal = draw(st.floats(min_value=0.01, max_value=0.20, allow_nan=False))
    inflation = draw(
        st.floats(
            min_value=0.0,
            max_value=max(nominal - 0.001, 0.0),
            allow_nan=False,
            allow_infinity=False,
        )
    )
    spending = draw(
        st.floats(
            min_value=10_000.0,
            max_value=200_000.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    portfolio = draw(
        st.floats(
            min_value=0.0,
            max_value=1_000_000.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    return FIInputs(
        current_age=current_age,
        retirement_age=retirement_age,
        current_portfolio=portfolio,
        monthly_contribution=0.0,
        annual_spending=spending,
        nominal_return_rate=nominal,
        inflation_rate=inflation,
    )


@given(inputs=_valid_inputs())
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_success_rate_in_bounds(inputs: FIInputs) -> None:
    result = run_simulation(inputs, n_simulations=100, rng_seed=13)
    assert 0.0 <= result.success_rate <= 1.0


@given(inputs=_valid_inputs())
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_percentile_band_lengths_match_ages(inputs: FIInputs) -> None:
    result = run_simulation(inputs, n_simulations=100, rng_seed=17)
    expected = len(result.ages)
    for band in result.percentile_bands.values():
        assert len(band) == expected
