"""Calculator page — placeholder.

Full implementation in Phase 6. This stub ensures Dash routing
initializes without errors during Phase 1.
"""

import dash
import dash_mantine_components as dmc

dash.register_page(__name__, path="/", name="Calculator")

layout = dmc.Container(dmc.Text("Calculator — Phase 6"))
