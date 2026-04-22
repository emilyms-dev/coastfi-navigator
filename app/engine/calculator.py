"""FI calculation engine — Phase 2.

Pure functions for computing Coast FI, Full FI, and all related milestone
numbers. No side effects, no database calls, no global state.
All monetary values are floats in USD; all rates are decimals (not percentages).
"""
