"""Monte Carlo simulation engine — Phase 2.

Runs stochastic portfolio projections using normally distributed annual returns
and inflation. Returns a structured result object with percentile bands, success
rate, and input echo. Uses ``numpy.random.default_rng()`` for a seedable,
reproducible RNG. The simulation is fully vectorized across runs — there is
never a Python-level loop over simulations, only (optionally) over years.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from app.engine.calculator import FIInputs, calculate_fi_number

_PERCENTILES: tuple[int, ...] = (10, 25, 50, 75, 90)
# Historical standard deviations are fixed — they model the empirical spread
# of S&P 500 annual returns and US CPI inflation. The means come from the
# user's own assumptions (inputs.nominal_return_rate, inputs.inflation_rate),
# so that scenario analysis varies the expected return while keeping volatility
# grounded in historical data.
_RETURN_STD: float = 0.15
_INFLATION_STD: float = 0.01


@dataclass
class SimulationResult:
    """Structured output of a Monte Carlo simulation run.

    Attributes:
        percentile_bands: Mapping from percentile (10, 25, 50, 75, 90) to a list
            of portfolio values in USD — one entry per year from ``current_age``
            through ``retirement_age`` inclusive.
        success_rate: Fraction of simulation runs where the final portfolio met
            or exceeded ``fi_number``. Always in [0.0, 1.0].
        n_simulations: Number of simulation runs executed.
        ages: Age labels matching each entry in each percentile band, covering
            ``current_age`` through ``retirement_age`` inclusive.
        fi_number: The FI target in USD used to evaluate run success.
        inputs_snapshot: Plain-dict echo of the FIInputs used, for storage and
            auditability.
    """

    percentile_bands: dict[int, list[float]]
    success_rate: float
    n_simulations: int
    ages: list[int]
    fi_number: float
    inputs_snapshot: dict = field(default_factory=dict)


def run_simulation(
    inputs: FIInputs,
    n_simulations: int = 1000,
    rng_seed: int | None = None,
) -> SimulationResult:
    """Run a vectorized Monte Carlo portfolio projection.

    Each simulated year samples an annual nominal return from
    ``Normal(inputs.nominal_return_rate, 0.15)`` and an annual inflation rate
    from ``Normal(inputs.inflation_rate, 0.01)``. The standard deviations are
    grounded in historical S&P 500 / CPI data; the means come from the user's
    stated assumptions so that what-if scenarios vary the expected return while
    keeping volatility realistic. The real return is computed per year per run,
    and the portfolio compounds across years without new contributions — this
    matches the Coast FI definition (no additional savings after today).

    Args:
        inputs: Validated FIInputs instance.
        n_simulations: Number of independent simulation runs. Defaults to 1000.
        rng_seed: Optional seed for ``numpy.random.default_rng``. When ``None``
            (the default), each call produces fresh randomness. Tests should
            pass a fixed integer here for reproducibility.

    Returns:
        A SimulationResult with percentile bands at every age, the fraction of
        successful runs, the number of runs executed, the age labels, the FI
        target used, and an echo of the inputs.

    Raises:
        ValueError: If any field in ``inputs`` fails validation or if
            ``n_simulations`` is less than 1.
    """
    inputs.validate()
    if n_simulations < 1:
        raise ValueError(f"n_simulations ({n_simulations}) must be at least 1")

    years_to_retirement = inputs.retirement_age - inputs.current_age
    ages = list(range(inputs.current_age, inputs.retirement_age + 1))
    fi_number = calculate_fi_number(inputs.annual_spending, multiplier=25.0)

    rng = np.random.default_rng(rng_seed)

    # Shape: (n_simulations, years_to_retirement). One nominal return and one
    # inflation sample per (run, year) — real return = nominal - inflation.
    nominal_returns = rng.normal(
        loc=inputs.nominal_return_rate,
        scale=_RETURN_STD,
        size=(n_simulations, years_to_retirement),
    )
    inflation_draws = rng.normal(
        loc=inputs.inflation_rate,
        scale=_INFLATION_STD,
        size=(n_simulations, years_to_retirement),
    )
    real_returns = nominal_returns - inflation_draws

    # Compound growth factors per run per year, then cumulative product gives
    # the multiplier applied to the starting portfolio up to and including
    # each year. Coast FI assumes no new contributions after today.
    # Clamp to 0.01 to prevent sign-flipping from extreme left-tail draws
    # (theoretical probability ~5e-8 per sample at normal inputs).
    growth_factors = np.maximum(1.0 + real_returns, 0.01)
    cumulative_growth = np.cumprod(growth_factors, axis=1)
    portfolio_paths = inputs.current_portfolio * cumulative_growth

    # Prepend the starting portfolio column so paths cover current_age through
    # retirement_age inclusive (years_to_retirement + 1 columns).
    # dtype=float64 is explicit: integer portfolio inputs would otherwise
    # produce an integer-typed array and silently truncate growth calculations.
    starting_column = np.full(
        (n_simulations, 1), inputs.current_portfolio, dtype=np.float64
    )
    portfolio_paths = np.concatenate([starting_column, portfolio_paths], axis=1)

    # Percentile bands across the simulation axis for every year.
    band_matrix = np.percentile(portfolio_paths, _PERCENTILES, axis=0)
    percentile_bands: dict[int, list[float]] = {
        pct: band_matrix[i].tolist() for i, pct in enumerate(_PERCENTILES)
    }

    final_portfolios = portfolio_paths[:, -1]
    success_rate = float(np.mean(final_portfolios >= fi_number))

    return SimulationResult(
        percentile_bands=percentile_bands,
        success_rate=success_rate,
        n_simulations=n_simulations,
        ages=ages,
        fi_number=fi_number,
        inputs_snapshot=asdict(inputs),
    )
