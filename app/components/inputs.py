"""Input panel component — Phase 6.

Builds the calculator input form as a dmc.Paper containing labelled
dmc.NumberInput fields for all FI calculation parameters.

Note on units: percentage inputs (return rate, inflation) are displayed and
stored as percentages (7.0 means 7%). The callback layer converts them to
decimals (0.07) before constructing FIInputs. This file never performs that
conversion.
"""

import dash_mantine_components as dmc


def get_input_panel() -> dmc.Paper:
    """Build the calculator input panel.

    Returns:
        A dmc.Paper containing labelled dmc.NumberInput fields for every
        FI calculation parameter.
    """
    return dmc.Paper(
        p="lg",
        withBorder=True,
        children=[
            dmc.Title("Your Numbers", order=4, mb="md"),
            dmc.Stack(
                gap="sm",
                children=[
                    dmc.NumberInput(
                        id="input-current-age",
                        label="Current Age",
                        min=18,
                        max=79,
                        step=1,
                        value=30,
                    ),
                    dmc.NumberInput(
                        id="input-retirement-age",
                        label="Target Retirement Age",
                        min=19,
                        max=80,
                        step=1,
                        value=65,
                    ),
                    dmc.NumberInput(
                        id="input-current-portfolio",
                        label="Current Portfolio ($)",
                        description="Total invested assets today",
                        min=0,
                        step=1000,
                        value=50000,
                    ),
                    dmc.NumberInput(
                        id="input-monthly-contribution",
                        label="Monthly Contribution ($)",
                        description="Amount added to portfolio each month",
                        min=0,
                        step=100,
                        value=1000,
                    ),
                    dmc.NumberInput(
                        id="input-annual-spending",
                        label="Annual Spending in Retirement ($)",
                        description="Estimated yearly expenses at retirement",
                        min=1000,
                        step=1000,
                        value=60000,
                    ),
                    dmc.NumberInput(
                        id="input-nominal-return",
                        label="Expected Annual Return (%)",
                        description="Historical S&P 500 average ~7%",
                        min=0.1,
                        max=30.0,
                        step=0.1,
                        value=7.0,
                        decimalScale=1,
                    ),
                    dmc.NumberInput(
                        id="input-inflation-rate",
                        label="Inflation Rate (%)",
                        description="Historical average ~3%",
                        min=0.1,
                        max=20.0,
                        step=0.1,
                        value=3.0,
                        decimalScale=1,
                    ),
                    dmc.NumberInput(
                        id="input-barista-income",
                        label="Part-time Income ($)",
                        description=(
                            "Annual income covering Barista FI gap (optional)"
                        ),
                        min=0,
                        step=500,
                        value=0,
                    ),
                ],
            ),
        ],
    )
