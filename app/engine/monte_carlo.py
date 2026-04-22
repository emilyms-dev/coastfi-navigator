"""Monte Carlo simulation engine — Phase 2.

Runs stochastic portfolio projections using normally distributed annual returns
and inflation. Returns a structured result object with percentile bands, success
rate, and median projection series. Uses numpy.random.default_rng() for a
seedable, reproducible RNG.
"""
