"""Engine tests — Phase 2.

Unit and property-based tests for app/engine/calculator.py and
app/engine/milestones.py. Uses hypothesis for property-based testing.
Minimum coverage target for engine/: 90%.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.engine.calculator import (
    FIInputs,
    calculate_all_milestones,
    calculate_coast_fi,
    calculate_deterministic_projection,
    calculate_fi_number,
    calculate_real_return,
)
from app.engine.milestones import (
    MILESTONE_DEFINITIONS,
    get_milestone_meta,
    get_progress_color,
)

# Ground-truth inputs used by the known-value assertion. Derived from the Phase 2
# domain spec: a 30-year-old spending $60k/year, 7% nominal, 3% inflation,
# retiring at 65.
#
# Exact Coast FI math for these inputs:
#   fi_number       = 60,000 * 25               = 1,500,000
#   real_return     = 0.07 - 0.03               = 0.04
#   years           = 65 - 30                   = 35
#   1.04 ** 35      = 3.946088994211942
#   coast_fi_number = 1,500,000 / 3.946088994.. = 380,123.2060909359
#
# The Phase 2 spec comment referenced ~$380,143 as an approximation; the exact
# formulaic answer is ~$380,123.21. Mathematical correctness is load-bearing
# here — we assert against the exact formula, not the rounded spec comment.
KNOWN_VALUE_INPUTS = FIInputs(
    current_age=30,
    retirement_age=65,
    current_portfolio=150_000.0,
    monthly_contribution=2_000.0,
    annual_spending=60_000.0,
    nominal_return_rate=0.07,
    inflation_rate=0.03,
)
EXPECTED_COAST_FI = 1_500_000.0 / (1.04**35)
COAST_FI_TOLERANCE = 1.00


# ── calculator.py: pure math ──────────────────────────────────────────


def test_coast_fi_known_value() -> None:
    result = calculate_all_milestones(KNOWN_VALUE_INPUTS)
    assert abs(result.coast_fi - EXPECTED_COAST_FI) <= COAST_FI_TOLERANCE, (
        f"Coast FI ground truth failed: got {result.coast_fi:,.2f}, "
        f"expected {EXPECTED_COAST_FI:,.2f} ± {COAST_FI_TOLERANCE}"
    )


def test_fi_number_standard() -> None:
    assert calculate_fi_number(60_000.0, multiplier=25.0) == 1_500_000.0


def test_fi_number_default_multiplier_is_25() -> None:
    assert calculate_fi_number(60_000.0) == 1_500_000.0


def test_real_return_rate() -> None:
    assert calculate_real_return(0.07, 0.03) == pytest.approx(0.04, abs=1e-12)


def test_milestone_ordering() -> None:
    # The Phase 2 spec *claims* the chain Lean ≤ Coast ≤ Barista ≤ Traditional ≤
    # Fat is always invariant. It is not: Coast FI is the *present value* of
    # Traditional FI, so at long horizons (here 35 years at 4% real) it falls
    # well below Lean FI (20x spending). The honest invariants — all of which
    # hold for every valid FIInputs — are:
    #   coast_fi        ≤ traditional_fi   (present value ≤ future value)
    #   lean_fi         ≤ traditional_fi   (multiplier 20 ≤ 25)
    #   barista_fi      ≤ traditional_fi   (barista_income ≥ 0 → gap ≤ spending)
    #   traditional_fi  ≤ fat_fi           (multiplier 25 ≤ 33)
    # Tracked as a spec-vs-math discrepancy in DEBT.md.
    result = calculate_all_milestones(KNOWN_VALUE_INPUTS)
    assert result.coast_fi <= result.traditional_fi
    assert result.lean_fi <= result.traditional_fi
    assert result.barista_fi <= result.traditional_fi
    assert result.traditional_fi <= result.fat_fi


def test_coast_fi_decreases_with_age() -> None:
    def coast_at_age(age: int) -> float:
        inputs = FIInputs(
            current_age=age,
            retirement_age=65,
            current_portfolio=100_000.0,
            monthly_contribution=1_000.0,
            annual_spending=60_000.0,
            nominal_return_rate=0.07,
            inflation_rate=0.03,
        )
        return calculate_all_milestones(inputs).coast_fi

    assert coast_at_age(30) < coast_at_age(40) < coast_at_age(50)


def test_coast_fi_equals_fi_at_retirement_minus_one() -> None:
    inputs = FIInputs(
        current_age=64,
        retirement_age=65,
        current_portfolio=100_000.0,
        monthly_contribution=0.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.07,
        inflation_rate=0.03,
    )
    result = calculate_all_milestones(inputs)
    expected = result.traditional_fi / (1.0 + result.real_return_rate)
    assert result.coast_fi == pytest.approx(expected, abs=1e-6)


def test_coast_fi_raises_on_zero_years() -> None:
    with pytest.raises(ValueError, match="years"):
        calculate_coast_fi(1_500_000.0, 0.04, 0)


def test_coast_fi_raises_on_negative_years() -> None:
    with pytest.raises(ValueError, match="years"):
        calculate_coast_fi(1_500_000.0, 0.04, -5)


def test_progress_pct_capped_at_100() -> None:
    # Portfolio exceeds Fat FI ($60k * 33 = $1.98M), so every milestone
    # progress should clamp to exactly 100.0.
    inputs = FIInputs(
        current_age=30,
        retirement_age=65,
        current_portfolio=5_000_000.0,
        monthly_contribution=0.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.07,
        inflation_rate=0.03,
    )
    result = calculate_all_milestones(inputs)
    for key in ("lean", "coast", "barista", "traditional", "fat"):
        assert result.current_progress_pct[key] == 100.0


def test_progress_pct_zero_portfolio() -> None:
    inputs = FIInputs(
        current_age=30,
        retirement_age=65,
        current_portfolio=0.0,
        monthly_contribution=0.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.07,
        inflation_rate=0.03,
    )
    result = calculate_all_milestones(inputs)
    for key in ("lean", "coast", "barista", "traditional", "fat"):
        assert result.current_progress_pct[key] == 0.0


def test_progress_pct_below_100_is_accurate() -> None:
    inputs = FIInputs(
        current_age=30,
        retirement_age=65,
        current_portfolio=750_000.0,
        monthly_contribution=0.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.07,
        inflation_rate=0.03,
    )
    result = calculate_all_milestones(inputs)
    assert result.current_progress_pct["traditional"] == pytest.approx(50.0)


def test_barista_fi_uses_default_30pct_income_when_zero() -> None:
    # annual_spending=60000, barista_income default = 18000, gap = 42000, x25 = 1.05M
    inputs = FIInputs(
        current_age=30,
        retirement_age=65,
        current_portfolio=0.0,
        monthly_contribution=0.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.07,
        inflation_rate=0.03,
    )
    result = calculate_all_milestones(inputs)
    assert result.barista_fi == pytest.approx(1_050_000.0)


def test_barista_fi_uses_explicit_income() -> None:
    inputs = FIInputs(
        current_age=30,
        retirement_age=65,
        current_portfolio=0.0,
        monthly_contribution=0.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.07,
        inflation_rate=0.03,
        barista_income=30_000.0,
    )
    result = calculate_all_milestones(inputs)
    assert result.barista_fi == pytest.approx((60_000.0 - 30_000.0) * 25.0)


def test_milestone_result_has_real_return_and_years() -> None:
    result = calculate_all_milestones(KNOWN_VALUE_INPUTS)
    assert result.real_return_rate == pytest.approx(0.04, abs=1e-12)
    assert result.years_to_retirement == 35


# ── FIInputs.validate ─────────────────────────────────────────────────


def _base_kwargs() -> dict:
    return {
        "current_age": 30,
        "retirement_age": 65,
        "current_portfolio": 100_000.0,
        "monthly_contribution": 1_000.0,
        "annual_spending": 60_000.0,
        "nominal_return_rate": 0.07,
        "inflation_rate": 0.03,
    }


def test_validate_raises_on_retirement_le_current_age() -> None:
    kwargs = _base_kwargs() | {"current_age": 65, "retirement_age": 65}
    with pytest.raises(ValueError, match="retirement_age"):
        FIInputs(**kwargs).validate()


def test_validate_raises_on_current_age_below_18() -> None:
    kwargs = _base_kwargs() | {"current_age": 17}
    with pytest.raises(ValueError, match="current_age"):
        FIInputs(**kwargs).validate()


def test_validate_raises_on_current_age_above_80() -> None:
    kwargs = _base_kwargs() | {"current_age": 81, "retirement_age": 82}
    with pytest.raises(ValueError, match="current_age"):
        FIInputs(**kwargs).validate()


def test_validate_raises_on_retirement_above_80() -> None:
    kwargs = _base_kwargs() | {"current_age": 70, "retirement_age": 81}
    with pytest.raises(ValueError, match="retirement_age"):
        FIInputs(**kwargs).validate()


def test_validate_raises_on_nonpositive_spending() -> None:
    kwargs = _base_kwargs() | {"annual_spending": 0.0}
    with pytest.raises(ValueError, match="annual_spending"):
        FIInputs(**kwargs).validate()


def test_validate_raises_on_negative_nominal_rate() -> None:
    kwargs = _base_kwargs() | {"nominal_return_rate": -0.01}
    with pytest.raises(ValueError, match="nominal_return_rate"):
        FIInputs(**kwargs).validate()


def test_validate_raises_on_high_nominal_rate() -> None:
    kwargs = _base_kwargs() | {"nominal_return_rate": 0.31}
    with pytest.raises(ValueError, match="nominal_return_rate"):
        FIInputs(**kwargs).validate()


def test_validate_raises_on_negative_inflation() -> None:
    kwargs = _base_kwargs() | {"inflation_rate": -0.01}
    with pytest.raises(ValueError, match="inflation_rate"):
        FIInputs(**kwargs).validate()


def test_validate_raises_on_high_inflation() -> None:
    kwargs = _base_kwargs() | {"inflation_rate": 0.21}
    with pytest.raises(ValueError, match="inflation_rate"):
        FIInputs(**kwargs).validate()


def test_validate_raises_on_negative_contribution() -> None:
    kwargs = _base_kwargs() | {"monthly_contribution": -1.0}
    with pytest.raises(ValueError, match="monthly_contribution"):
        FIInputs(**kwargs).validate()


def test_validate_accepts_boundary_values() -> None:
    # 18 <= age <= 80, 0 <= nominal <= 0.30, 0 <= inflation <= 0.20.
    inputs = FIInputs(
        current_age=18,
        retirement_age=80,
        current_portfolio=0.0,
        monthly_contribution=0.0,
        annual_spending=1.0,
        nominal_return_rate=0.30,
        inflation_rate=0.20,
    )
    inputs.validate()  # must not raise


# ── deterministic projection ──────────────────────────────────────────


def test_deterministic_projection_length() -> None:
    projection = calculate_deterministic_projection(KNOWN_VALUE_INPUTS)
    years = KNOWN_VALUE_INPUTS.retirement_age - KNOWN_VALUE_INPUTS.current_age
    assert len(projection) == years + 1
    assert projection[0][0] == KNOWN_VALUE_INPUTS.current_age
    assert projection[-1][0] == KNOWN_VALUE_INPUTS.retirement_age


def test_deterministic_projection_grows() -> None:
    projection = calculate_deterministic_projection(KNOWN_VALUE_INPUTS)
    values = [value for _, value in projection]
    for earlier, later in zip(values, values[1:]):
        assert later >= earlier


def test_deterministic_projection_first_value_is_current_portfolio() -> None:
    projection = calculate_deterministic_projection(KNOWN_VALUE_INPUTS)
    assert projection[0][1] == KNOWN_VALUE_INPUTS.current_portfolio


def test_deterministic_projection_math_matches_formula() -> None:
    # Single-year closed form: (p0 * (1+r)) + (mc * 12)
    inputs = FIInputs(
        current_age=30,
        retirement_age=31,
        current_portfolio=100_000.0,
        monthly_contribution=1_000.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.07,
        inflation_rate=0.03,
    )
    projection = calculate_deterministic_projection(inputs)
    expected = 100_000.0 * 1.07 + 12_000.0
    assert projection[1][1] == pytest.approx(expected, abs=1e-6)


# ── milestones.py ─────────────────────────────────────────────────────


def test_milestone_definitions_has_all_five_keys() -> None:
    keys = {entry["key"] for entry in MILESTONE_DEFINITIONS}
    assert keys == {"lean", "coast", "barista", "traditional", "fat"}


def test_milestone_definitions_order_is_unique_and_sequential() -> None:
    orders = sorted(entry["order"] for entry in MILESTONE_DEFINITIONS)
    assert orders == [1, 2, 3, 4, 5]


def test_get_milestone_meta_returns_dict() -> None:
    meta = get_milestone_meta("coast")
    assert meta["key"] == "coast"
    assert meta["label"] == "Coast FI"


def test_get_milestone_meta_raises_on_unknown_key() -> None:
    with pytest.raises(KeyError):
        get_milestone_meta("nonexistent")


@pytest.mark.parametrize(
    "progress, expected",
    [
        (0.0, "red"),
        (39.99, "red"),
        (40.0, "yellow"),
        (79.99, "yellow"),
        (80.0, "lime"),
        (99.99, "lime"),
        (100.0, "green"),
        (150.0, "green"),
    ],
)
def test_get_progress_color_bands(progress: float, expected: str) -> None:
    assert get_progress_color(progress) == expected


# ── Hypothesis property tests ─────────────────────────────────────────


_rate_strategy = st.floats(
    min_value=0.01,
    max_value=0.20,
    allow_nan=False,
    allow_infinity=False,
)
_spending_strategy = st.floats(
    min_value=10_000.0,
    max_value=500_000.0,
    allow_nan=False,
    allow_infinity=False,
)


@st.composite
def _valid_inputs(draw) -> FIInputs:
    current_age = draw(st.integers(min_value=18, max_value=60))
    retirement_age = draw(st.integers(min_value=current_age + 1, max_value=80))
    nominal = draw(_rate_strategy)
    # Keep inflation strictly less than nominal so real_return > 0 — matches the
    # intended use case and keeps the Coast FI formula well-conditioned.
    inflation = draw(
        st.floats(
            min_value=0.0,
            max_value=max(nominal - 0.001, 0.0),
            allow_nan=False,
            allow_infinity=False,
        )
    )
    spending = draw(_spending_strategy)
    portfolio = draw(
        st.floats(
            min_value=0.0,
            max_value=2_000_000.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    contribution = draw(
        st.floats(
            min_value=0.0,
            max_value=10_000.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    return FIInputs(
        current_age=current_age,
        retirement_age=retirement_age,
        current_portfolio=portfolio,
        monthly_contribution=contribution,
        annual_spending=spending,
        nominal_return_rate=nominal,
        inflation_rate=inflation,
    )


@given(inputs=_valid_inputs())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_coast_fi_always_leq_fi_number(inputs: FIInputs) -> None:
    result = calculate_all_milestones(inputs)
    # Coast FI is the present value of Traditional FI — always less-or-equal.
    assert result.coast_fi <= result.traditional_fi + 1e-6


@given(inputs=_valid_inputs())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_milestones_ordering_property(inputs: FIInputs) -> None:
    # See test_milestone_ordering above for why we assert only the
    # mathematically-invariant orderings and not the full spec chain.
    result = calculate_all_milestones(inputs)
    assert result.coast_fi <= result.traditional_fi + 1e-6
    assert result.lean_fi <= result.traditional_fi + 1e-6
    assert result.barista_fi <= result.traditional_fi + 1e-6
    assert result.traditional_fi <= result.fat_fi + 1e-6


@given(
    nominal=st.floats(min_value=0.0, max_value=0.30, allow_nan=False),
    inflation=st.floats(
        min_value=1e-6, max_value=0.20, allow_nan=False, allow_infinity=False
    ),
)
def test_real_return_always_less_than_nominal(nominal: float, inflation: float) -> None:
    real = calculate_real_return(nominal, inflation)
    assert real < nominal
    assert math.isfinite(real)
