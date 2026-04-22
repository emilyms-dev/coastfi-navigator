"""FI calculation engine — Phase 2.

Pure functions for computing Coast FI, Full FI, and all related milestone
numbers. No side effects, no database calls, no global state.
All monetary values are floats in USD; all rates are decimals (not percentages).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FIInputs:
    """User-provided inputs to the FI calculation engine.

    All rates are decimals (0.07 means 7%). All monetary values are floats in USD.
    Every engine-level function accepts an instance of this dataclass rather than
    individual parameters so that signatures remain stable as inputs evolve.

    Attributes:
        current_age: Current age of the user in whole years.
        retirement_age: Target retirement age in whole years.
        current_portfolio: Current invested portfolio value in USD.
        monthly_contribution: Monthly savings contribution in USD.
        annual_spending: Expected annual spending in retirement, USD.
        nominal_return_rate: Expected nominal annual return as decimal (e.g. 0.07).
        inflation_rate: Expected annual inflation as decimal (e.g. 0.03).
        lean_multiplier: Multiplier used to compute the Lean FI number. Default 20
            corresponds to a 5% safe withdrawal rate.
        barista_income: Annual part-time income that would offset expenses in the
            Barista FI scenario, USD. Default 0.0 means caller should derive it.
    """

    current_age: int
    retirement_age: int
    current_portfolio: float
    monthly_contribution: float
    annual_spending: float
    nominal_return_rate: float
    inflation_rate: float
    lean_multiplier: float = 20.0
    barista_income: float = 0.0

    def validate(self) -> None:
        """Validate input values and raise ValueError on any invalid state.

        Raises:
            ValueError: If any field is outside its acceptable range. Each invalid
                state produces a descriptive message identifying the field and
                the constraint that was violated.
        """
        if self.retirement_age <= self.current_age:
            raise ValueError(
                f"retirement_age ({self.retirement_age}) must be greater than "
                f"current_age ({self.current_age})"
            )
        if self.current_age < 18 or self.current_age > 80:
            raise ValueError(
                f"current_age ({self.current_age}) must be between 18 and 80"
            )
        if self.retirement_age > 80:
            raise ValueError(
                f"retirement_age ({self.retirement_age}) must be at most 80"
            )
        if self.annual_spending <= 0:
            raise ValueError(
                f"annual_spending ({self.annual_spending}) must be positive"
            )
        if self.nominal_return_rate < 0 or self.nominal_return_rate > 0.30:
            raise ValueError(
                f"nominal_return_rate ({self.nominal_return_rate}) must be "
                f"between 0 and 0.30 (decimal form)"
            )
        if self.inflation_rate < 0 or self.inflation_rate > 0.20:
            raise ValueError(
                f"inflation_rate ({self.inflation_rate}) must be between 0 and "
                f"0.20 (decimal form)"
            )
        if self.monthly_contribution < 0:
            raise ValueError(
                f"monthly_contribution ({self.monthly_contribution}) must be "
                f"non-negative"
            )


@dataclass
class MilestoneResult:
    """Structured output of calculate_all_milestones.

    Attributes:
        lean_fi: Lean FI target in USD (annual_spending * lean_multiplier).
        coast_fi: Coast FI target in USD — present value of the Traditional FI
            number discounted by the real return rate over years to retirement.
        barista_fi: Barista FI target in USD — covers spending minus part-time
            income at a 4% withdrawal rate.
        traditional_fi: Traditional FI target in USD (annual_spending * 25).
        fat_fi: Fat FI target in USD (annual_spending * 33).
        real_return_rate: Inflation-adjusted return rate as decimal.
        years_to_retirement: Years from current_age to retirement_age.
        current_progress_pct: Mapping of milestone key ("lean", "coast",
            "barista", "traditional", "fat") to current portfolio progress as a
            percentage, capped at 100.0.
    """

    lean_fi: float
    coast_fi: float
    barista_fi: float
    traditional_fi: float
    fat_fi: float
    real_return_rate: float
    years_to_retirement: int
    current_progress_pct: dict[str, float] = field(default_factory=dict)


def calculate_real_return(nominal_rate: float, inflation_rate: float) -> float:
    """Compute the real (inflation-adjusted) return rate.

    Uses the Fisher-equation approximation ``real = nominal - inflation``.
    This approximation is standard for FI planning and matches the Coast FI
    formulation expected by the rest of the engine.

    Args:
        nominal_rate: Nominal annual return as a decimal (e.g. 0.07).
        inflation_rate: Annual inflation as a decimal (e.g. 0.03).

    Returns:
        The real annual return rate as a decimal.
    """
    return nominal_rate - inflation_rate


def calculate_fi_number(annual_spending: float, multiplier: float = 25.0) -> float:
    """Compute a generic FI number from annual spending and a withdrawal multiplier.

    Args:
        annual_spending: Annual spending target in USD.
        multiplier: Withdrawal multiplier. Default 25 corresponds to the 4% rule.

    Returns:
        The FI number in USD (annual_spending * multiplier).
    """
    return annual_spending * multiplier


def calculate_coast_fi(fi_number: float, real_return_rate: float, years: int) -> float:
    """Compute the Coast FI number — the present value of the FI number.

    The Coast FI number is the portfolio value that, left completely untouched
    (no further contributions), would compound at the real return rate to equal
    the FI number at retirement.

    Args:
        fi_number: The future FI target in USD.
        real_return_rate: Inflation-adjusted return rate as a decimal.
        years: Whole years between now and retirement. Must be greater than 0.

    Returns:
        The Coast FI number in USD.

    Raises:
        ValueError: If ``years`` is less than or equal to 0.
    """
    if years <= 0:
        raise ValueError(f"years ({years}) must be greater than 0 to compute Coast FI")
    return fi_number / ((1.0 + real_return_rate) ** years)


def calculate_all_milestones(inputs: FIInputs) -> MilestoneResult:
    """Compute every FI milestone and progress percentage from a single input set.

    This is the primary public entry point for the UI layer. Input validation is
    performed here — callers do not need to call ``inputs.validate()`` separately.

    Milestones produced:
        * Lean FI       = annual_spending * lean_multiplier
        * Coast FI      = Traditional FI / (1 + real_return)^years
        * Barista FI    = (annual_spending - barista_income) * 25
        * Traditional FI = annual_spending * 25
        * Fat FI        = annual_spending * 33

    Barista income defaults to 30% of annual spending when not explicitly set.

    Args:
        inputs: Validated FIInputs instance.

    Returns:
        A MilestoneResult with every milestone, the real return rate, years to
        retirement, and the user's current progress toward each milestone as a
        percentage capped at 100.0.

    Raises:
        ValueError: If any field in ``inputs`` fails validation.
    """
    inputs.validate()

    real_return_rate = calculate_real_return(
        inputs.nominal_return_rate, inputs.inflation_rate
    )
    years_to_retirement = inputs.retirement_age - inputs.current_age

    traditional_fi = calculate_fi_number(inputs.annual_spending, multiplier=25.0)
    lean_fi = calculate_fi_number(
        inputs.annual_spending, multiplier=inputs.lean_multiplier
    )
    fat_fi = calculate_fi_number(inputs.annual_spending, multiplier=33.0)

    # Barista income defaults to 30% of annual spending when caller left it at 0.
    barista_income = (
        inputs.barista_income
        if inputs.barista_income > 0.0
        else inputs.annual_spending * 0.30
    )
    barista_gap = max(inputs.annual_spending - barista_income, 0.0)
    barista_fi = barista_gap * 25.0

    coast_fi = calculate_coast_fi(traditional_fi, real_return_rate, years_to_retirement)

    milestones = {
        "lean": lean_fi,
        "coast": coast_fi,
        "barista": barista_fi,
        "traditional": traditional_fi,
        "fat": fat_fi,
    }
    progress_pct = {
        key: _progress_toward(inputs.current_portfolio, target)
        for key, target in milestones.items()
    }

    return MilestoneResult(
        lean_fi=lean_fi,
        coast_fi=coast_fi,
        barista_fi=barista_fi,
        traditional_fi=traditional_fi,
        fat_fi=fat_fi,
        real_return_rate=real_return_rate,
        years_to_retirement=years_to_retirement,
        current_progress_pct=progress_pct,
    )


def _progress_toward(current: float, target: float) -> float:
    """Progress percentage of ``current`` toward ``target``, capped at 100.0."""
    if target <= 0:
        return 100.0 if current > 0 else 0.0
    return min((current / target) * 100.0, 100.0)


def calculate_deterministic_projection(
    inputs: FIInputs,
) -> list[tuple[int, float]]:
    """Compute a deterministic year-by-year portfolio projection.

    Applies the user's fixed nominal return rate and adds annualized monthly
    contributions at the end of each year. This is the reference line shown on
    the fan chart alongside the Monte Carlo bands — it is not itself stochastic.

    Args:
        inputs: Validated FIInputs instance.

    Returns:
        List of ``(age, portfolio_value)`` tuples from ``current_age`` to
        ``retirement_age`` inclusive. The first tuple is the starting portfolio
        at ``current_age``.

    Raises:
        ValueError: If any field in ``inputs`` fails validation.
    """
    inputs.validate()

    annual_contribution = inputs.monthly_contribution * 12.0
    portfolio = inputs.current_portfolio
    projection: list[tuple[int, float]] = [(inputs.current_age, portfolio)]

    for age in range(inputs.current_age + 1, inputs.retirement_age + 1):
        portfolio = portfolio * (1.0 + inputs.nominal_return_rate) + annual_contribution
        projection.append((age, portfolio))

    return projection
