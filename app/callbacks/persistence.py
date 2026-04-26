"""Persistence callbacks — Phase 7.

Handles saving, loading, deleting, and sharing scenarios. All database
interactions go through app/db/crud.py — no direct session usage here.

Auth state is read exclusively from store-auth-state; these callbacks never
call get_current_user() or touch the Flask session directly.

Callback registration order within this file determines which callback
"owns" a given output (the first one without allow_duplicate=True):
  - save_scenario    owns: notifications-container, store-active-scenario-id
  - delete_scenario  owns: dashboard-scenario-list
  - load_scenario    uses allow_duplicate=True for all shared outputs
  - generate_share_link  uses allow_duplicate=True for notifications-container
  - load_dashboard_scenarios  uses allow_duplicate=True for dashboard-scenario-list
"""

from __future__ import annotations

import logging

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, ctx, no_update
from dash.exceptions import PreventUpdate

from app.components.scenario_card import get_scenario_card
from app.db import crud

logger = logging.getLogger(__name__)


# ── Helper ────────────────────────────────────────────────────────────────────


def _notification(
    title: str,
    message: str,
    color: str,
) -> dmc.Notification:
    """Build a dmc.Notification for the notifications-container.

    Args:
        title: Short notification title.
        message: Descriptive message body.
        color: Mantine color token ("green", "red", "blue").

    Returns:
        A dmc.Notification component with action="show".
    """
    return dmc.Notification(
        id="active-notification",
        title=title,
        message=message,
        color=color,
        action="show",
        autoClose=4000,
    )


# ── Save scenario ─────────────────────────────────────────────────────────────


@callback(
    Output("notifications-container", "children"),
    Output("store-active-scenario-id", "data"),
    Input("btn-save-scenario", "n_clicks"),
    State("store-auth-state", "data"),
    State("store-user-inputs", "data"),
    State("store-simulation-results", "data"),
    State("input-save-scenario-name", "value"),
    prevent_initial_call=True,
)
def save_scenario(
    n_clicks: int | None,
    auth_state: dict | None,
    user_inputs: str | None,
    sim_results: str | None,
    scenario_name: str | None,
) -> tuple:
    """Save the current calculator state as a new scenario snapshot.

    Unauthenticated users receive a prompt to sign in rather than an error.
    Every save creates a new snapshot row — no existing rows are modified.

    Args:
        n_clicks: Click count from the Save button.
        auth_state: Current auth store payload.
        user_inputs: JSON-serialised FIInputs from store-user-inputs.
        sim_results: JSON-serialised SimulationResult from store-simulation-results.
        scenario_name: Text input value for the scenario name.

    Returns:
        Tuple of (notification, active_scenario_id).
    """
    if not n_clicks:
        raise PreventUpdate

    auth_state = auth_state or {}

    if not auth_state.get("authenticated"):
        return (
            _notification(
                "Sign in to save",
                "Sign in to save your scenario.",
                "blue",
            ),
            no_update,
        )

    if not user_inputs:
        return (
            _notification("Nothing to save", "Run a calculation first.", "red"),
            no_update,
        )

    name = (scenario_name or "").strip() or "My Plan"

    try:
        scenario = crud.create_scenario(auth_state["user_id"], name)
        crud.save_snapshot(
            scenario_id=scenario.id,
            inputs_json=user_inputs,
            user_id=auth_state["user_id"],
            results_json=sim_results,
        )
        return (
            _notification("Saved", f'"{name}" saved successfully.', "green"),
            scenario.id,
        )
    except Exception:
        logger.exception("Error saving scenario for user %s", auth_state.get("user_id"))
        return (
            _notification(
                "Save failed", "Could not save scenario. Please try again.", "red"
            ),
            no_update,
        )


# ── Delete scenario ───────────────────────────────────────────────────────────


@callback(
    Output("dashboard-scenario-list", "children"),
    Output("notifications-container", "children", allow_duplicate=True),
    Input({"type": "btn-delete-scenario", "index": dash.ALL}, "n_clicks"),
    State("store-auth-state", "data"),
    prevent_initial_call=True,
)
def delete_scenario(
    n_clicks_list: list,
    auth_state: dict | None,
) -> tuple:
    """Delete a scenario and refresh the dashboard list.

    Uses pattern-matched inputs so any Delete button on any scenario card
    triggers this callback. ctx.triggered_id["index"] gives the scenario id.

    Args:
        n_clicks_list: List of click counts for all Delete buttons.
        auth_state: Current auth store payload.

    Returns:
        Tuple of (updated_scenario_list, notification).
    """
    if not any(n_clicks_list):
        raise PreventUpdate

    auth_state = auth_state or {}
    scenario_id = ctx.triggered_id["index"]

    deleted = crud.delete_scenario(scenario_id, auth_state.get("user_id", -1))

    # Rebuild the list regardless of deletion outcome.
    updated_list = _build_scenario_list(auth_state)

    if deleted:
        return updated_list, _notification("Deleted", "Scenario deleted.", "green")
    return updated_list, _notification("Error", "Could not delete scenario.", "red")


# ── Load scenario ─────────────────────────────────────────────────────────────


@callback(
    Output("store-user-inputs", "data", allow_duplicate=True),
    Output("store-simulation-results", "data", allow_duplicate=True),
    Output("store-active-scenario-id", "data", allow_duplicate=True),
    Output("url", "pathname"),
    Output("notifications-container", "children", allow_duplicate=True),
    Input({"type": "btn-load-scenario", "index": dash.ALL}, "n_clicks"),
    State("store-auth-state", "data"),
    prevent_initial_call=True,
)
def load_scenario(
    n_clicks_list: list,
    auth_state: dict | None,
) -> tuple:
    """Load a scenario's latest snapshot into the calculator stores.

    Navigates to "/" after loading so the calculator page reflects the
    restored inputs immediately.

    Args:
        n_clicks_list: List of click counts for all Load buttons.
        auth_state: Current auth store payload.

    Returns:
        Tuple of (user_inputs, sim_results, scenario_id, pathname, notification).
    """
    if not any(n_clicks_list):
        raise PreventUpdate

    _no_change = (no_update, no_update, no_update, no_update, no_update)

    auth_state = auth_state or {}
    scenario_id = ctx.triggered_id["index"]

    scenario = crud.get_scenario_by_id(scenario_id, auth_state.get("user_id", -1))
    if not scenario:
        notif = _notification("Error", "Scenario not found.", "red")
        return no_update, no_update, no_update, no_update, notif

    snapshot = crud.get_latest_snapshot(scenario_id, auth_state.get("user_id", -1))
    if not snapshot:
        notif = _notification("Empty", "This scenario has no saved data.", "blue")
        return no_update, no_update, no_update, no_update, notif

    notif = _notification("Loaded", f'"{scenario.name}" loaded.', "green")
    return (
        snapshot.inputs_json,
        snapshot.results_json,
        scenario.id,
        "/",
        notif,
    )


# ── Generate share link ───────────────────────────────────────────────────────


@callback(
    Output("notifications-container", "children", allow_duplicate=True),
    Input({"type": "btn-share-scenario", "index": dash.ALL}, "n_clicks"),
    State("store-auth-state", "data"),
    prevent_initial_call=True,
)
def generate_share_link(
    n_clicks_list: list,
    auth_state: dict | None,
) -> dmc.Notification:
    """Generate a share token for a scenario and surface the URL.

    Args:
        n_clicks_list: List of click counts for all Share buttons.
        auth_state: Current auth store payload.

    Returns:
        A dmc.Notification with the share URL.
    """
    if not any(n_clicks_list):
        raise PreventUpdate

    auth_state = auth_state or {}
    scenario_id = ctx.triggered_id["index"]

    try:
        token = crud.generate_share_token(scenario_id, auth_state.get("user_id", -1))
        share_url = f"/share/{token}"
        return dmc.Notification(
            id="active-notification",
            title="Share link ready",
            message=dmc.Text(
                [
                    "Share this link: ",
                    dmc.Anchor(share_url, href=share_url, target="_blank"),
                ]
            ),
            color="green",
            action="show",
            autoClose=8000,
        )
    except ValueError:
        return _notification("Error", "Could not generate share link.", "red")
    except Exception:
        logger.exception(
            "Unexpected error generating share token for scenario %s", scenario_id
        )
        return _notification("Error", "Could not generate share link.", "red")


# ── Load dashboard scenario list ──────────────────────────────────────────────


@callback(
    Output("dashboard-scenario-list", "children", allow_duplicate=True),
    Input("url", "pathname"),
    State("store-auth-state", "data"),
    # 'initial_duplicate' allows the callback to fire on initial page load
    # (needed when the user navigates directly to /dashboard) while still
    # satisfying Dash's rule that allow_duplicate requires prevent_initial_call.
    prevent_initial_call="initial_duplicate",
)
def load_dashboard_scenarios(
    pathname: str,
    auth_state: dict | None,
) -> list | dmc.Alert | dmc.Text:
    """Populate the dashboard scenario list when the user navigates to /dashboard.

    Only runs when pathname is "/dashboard" — other navigations are suppressed
    to avoid unnecessary DB queries and clearing an already-rendered list.

    Args:
        pathname: Current URL path from dcc.Location.
        auth_state: Current auth store payload.

    Returns:
        List of scenario cards, an alert, or a placeholder text component.
    """
    if pathname != "/dashboard":
        raise PreventUpdate

    auth_state = auth_state or {}
    return _build_scenario_list(auth_state)


# ── Shared helper ─────────────────────────────────────────────────────────────


def _build_scenario_list(
    auth_state: dict,
) -> list | dmc.Alert | dmc.Text:
    """Query and render the scenario list for the authenticated user.

    Args:
        auth_state: Current auth store payload.

    Returns:
        List of scenario cards, an unauthenticated alert, or an empty-state message.
    """
    if not auth_state.get("authenticated"):
        return dmc.Alert("Sign in to view your saved scenarios.", color="blue")

    scenarios = crud.get_scenarios_for_user(auth_state["user_id"])
    if not scenarios:
        return dmc.Text(
            "No saved scenarios yet. Calculate and save your first plan!",
            c="dimmed",
        )

    # snapshots are eagerly loaded by get_scenarios_for_user (selectinload),
    # so accessing s.snapshots on detached objects is safe here.
    return [
        get_scenario_card(s, s.snapshots[-1] if s.snapshots else None)
        for s in scenarios
    ]
