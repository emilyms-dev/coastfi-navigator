"""Database CRUD operations — Phase 3.

All database reads and writes go through functions defined here.
Callbacks must never call SQLAlchemy sessions directly or write raw SQL.

Sessions are managed with context managers inside each function.
No function yields or returns an open session to a caller.
"""

from __future__ import annotations

import dataclasses
import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models import Scenario, ScenarioSnapshot, User
from app.db.session import Session
from app.engine.calculator import FIInputs
from app.engine.monte_carlo import SimulationResult

# ── User operations ───────────────────────────────────────────────────


def create_user(email: str, password_hash: str) -> User:
    """Create and persist a new User.

    Args:
        email: The user's login email address. Must be unique.
        password_hash: Pre-computed bcrypt hash. Never the plaintext password.

    Returns:
        The newly created User with its database-assigned id populated.

    Raises:
        ValueError: If a user with the given email already exists.
    """
    with Session() as session:
        existing = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError(f"A user with email {email!r} already exists.")
        user = User(email=email, password_hash=password_hash)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def get_user_by_email(email: str) -> User | None:
    """Look up a User by email address.

    Args:
        email: The email to search for.

    Returns:
        The matching User, or None if no such user exists.
    """
    with Session() as session:
        return session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()


def get_user_by_id(user_id: int) -> User | None:
    """Look up a User by primary key.

    Args:
        user_id: The user's database id.

    Returns:
        The matching User, or None if not found.
    """
    with Session() as session:
        return session.get(User, user_id)


# ── Scenario operations ───────────────────────────────────────────────


def create_scenario(user_id: int, name: str) -> Scenario:
    """Create a new Scenario with no snapshots.

    Args:
        user_id: The id of the owning User.
        name: A user-defined label for the scenario.

    Returns:
        The newly created Scenario with its database-assigned id populated.
    """
    with Session() as session:
        scenario = Scenario(user_id=user_id, name=name)
        session.add(scenario)
        session.commit()
        session.refresh(scenario)
        return scenario


def get_scenarios_for_user(user_id: int) -> list[Scenario]:
    """Return all scenarios for a user, newest first.

    Eagerly loads all snapshots for each scenario to avoid N+1 queries
    when the dashboard renders preview cards.

    Args:
        user_id: The id of the owning User.

    Returns:
        List of Scenario objects ordered by created_at DESC, each with
        its snapshots already loaded.
    """
    with Session() as session:
        result = session.execute(
            select(Scenario)
            .where(Scenario.user_id == user_id)
            .options(selectinload(Scenario.snapshots))
            .order_by(Scenario.created_at.desc(), Scenario.id.desc())
        )
        return list(result.scalars().all())


def get_scenario_by_id(scenario_id: int, user_id: int) -> Scenario | None:
    """Return a Scenario only if it is owned by the given user.

    This function enforces ownership — it never returns a scenario to a
    caller who does not own it.

    Args:
        scenario_id: The scenario's database id.
        user_id: The id of the requesting user.

    Returns:
        The Scenario with snapshots loaded, or None if not found or if
        the scenario belongs to a different user.
    """
    with Session() as session:
        return session.execute(
            select(Scenario)
            .where(Scenario.id == scenario_id, Scenario.user_id == user_id)
            .options(selectinload(Scenario.snapshots))
        ).scalar_one_or_none()


def delete_scenario(scenario_id: int, user_id: int) -> bool:
    """Delete a scenario and all its snapshots.

    The cascade delete on Scenario.snapshots handles removing all child
    ScenarioSnapshot rows automatically.

    Args:
        scenario_id: The scenario's database id.
        user_id: The id of the requesting user (ownership check).

    Returns:
        True if the scenario was found and deleted, False if not found or
        if it belongs to a different user.
    """
    with Session() as session:
        scenario = session.execute(
            select(Scenario).where(
                Scenario.id == scenario_id, Scenario.user_id == user_id
            )
        ).scalar_one_or_none()
        if scenario is None:
            return False
        session.delete(scenario)
        session.commit()
        return True


def generate_share_token(scenario_id: int, user_id: int) -> str:
    """Return the share token for a scenario, creating one if needed.

    Idempotent — repeated calls for the same scenario return the same token.

    Args:
        scenario_id: The scenario's database id.
        user_id: The id of the requesting user (ownership check).

    Returns:
        The UUID4 string share token.

    Raises:
        ValueError: If the scenario is not found or not owned by user_id.
    """
    with Session() as session:
        scenario = session.execute(
            select(Scenario).where(
                Scenario.id == scenario_id, Scenario.user_id == user_id
            )
        ).scalar_one_or_none()
        if scenario is None:
            raise ValueError(
                f"Scenario {scenario_id} not found or not owned by user {user_id}."
            )
        if scenario.share_token is not None:
            return scenario.share_token
        token = str(uuid.uuid4())
        scenario.share_token = token
        session.commit()
        return token


def get_scenario_by_share_token(token: str) -> Scenario | None:
    """Return the Scenario for a public share token.

    No ownership check — the token itself is the authorization credential.
    Used exclusively by the read-only share view.

    Args:
        token: The UUID4 share token string.

    Returns:
        The matching Scenario with snapshots loaded, or None if the token
        does not match any scenario.
    """
    with Session() as session:
        return session.execute(
            select(Scenario)
            .where(Scenario.share_token == token)
            .options(selectinload(Scenario.snapshots))
        ).scalar_one_or_none()


# ── Snapshot operations ───────────────────────────────────────────────


def save_snapshot(
    scenario_id: int,
    inputs_json: str,
    user_id: int,
    results_json: str | None = None,
) -> ScenarioSnapshot:
    """Append a new immutable snapshot to a scenario.

    Verifies that ``user_id`` owns the scenario, then locks the scenario row
    with SELECT FOR UPDATE before reading MAX(version). The row lock serializes
    concurrent saves for the same scenario so that version numbers are assigned
    without gaps or duplicates. The unique constraint on (scenario_id, version)
    in the schema provides a final safety net.

    If no prior snapshots exist, version = 1. Never modifies an existing
    snapshot row — this function is the sole write path for snapshots.

    Args:
        scenario_id: The parent scenario's database id.
        inputs_json: JSON string produced by serialize_inputs().
        user_id: The id of the requesting user (ownership check).
        results_json: Optional JSON string produced by serialize_results().
            May be None if the user saves before running the simulation.

    Returns:
        The newly created ScenarioSnapshot with its id and version populated.

    Raises:
        ValueError: If the scenario is not found or not owned by user_id.
    """
    with Session() as session:
        # Lock the scenario row for the duration of this transaction.
        # This serializes concurrent saves for the same scenario and enforces
        # ownership in a single query. with_for_update() is a no-op on SQLite.
        scenario = session.execute(
            select(Scenario)
            .where(Scenario.id == scenario_id, Scenario.user_id == user_id)
            .with_for_update()
        ).scalar_one_or_none()
        if scenario is None:
            raise ValueError(
                f"Scenario {scenario_id} not found or not owned by user {user_id}."
            )
        max_version = session.execute(
            select(func.coalesce(func.max(ScenarioSnapshot.version), 0)).where(
                ScenarioSnapshot.scenario_id == scenario_id
            )
        ).scalar_one()
        snapshot = ScenarioSnapshot(
            scenario_id=scenario_id,
            version=max_version + 1,
            inputs_json=inputs_json,
            results_json=results_json,
        )
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)
        return snapshot


def get_snapshots_for_scenario(
    scenario_id: int,
    user_id: int,
    limit: int = 10,
) -> list[ScenarioSnapshot]:
    """Return recent snapshots for a scenario, newest first.

    Enforces ownership via a JOIN — returns an empty list if the scenario
    does not exist or is owned by a different user.

    Args:
        scenario_id: The parent scenario's database id.
        user_id: The id of the requesting user (ownership check).
        limit: Maximum number of snapshots to return. Defaults to 10.

    Returns:
        Up to ``limit`` ScenarioSnapshot objects ordered by version DESC,
        or an empty list if the scenario is not found or not owned by user_id.
    """
    with Session() as session:
        result = session.execute(
            select(ScenarioSnapshot)
            .join(Scenario, ScenarioSnapshot.scenario_id == Scenario.id)
            .where(
                ScenarioSnapshot.scenario_id == scenario_id,
                Scenario.user_id == user_id,
            )
            .order_by(ScenarioSnapshot.version.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


def get_latest_snapshot(scenario_id: int, user_id: int) -> ScenarioSnapshot | None:
    """Return the most recent snapshot for a scenario.

    Enforces ownership via a JOIN — returns None if the scenario does not
    exist or is owned by a different user.

    Args:
        scenario_id: The parent scenario's database id.
        user_id: The id of the requesting user (ownership check).

    Returns:
        The newest ScenarioSnapshot, or None if the scenario has no snapshots
        or is not owned by user_id.
    """
    with Session() as session:
        return session.execute(
            select(ScenarioSnapshot)
            .join(Scenario, ScenarioSnapshot.scenario_id == Scenario.id)
            .where(
                ScenarioSnapshot.scenario_id == scenario_id,
                Scenario.user_id == user_id,
            )
            .order_by(ScenarioSnapshot.version.desc())
            .limit(1)
        ).scalar_one_or_none()


# ── Serialization helpers ─────────────────────────────────────────────


def serialize_inputs(inputs: FIInputs) -> str:
    """Serialize a FIInputs dataclass to a JSON string.

    Args:
        inputs: The FIInputs instance to serialize.

    Returns:
        A JSON string suitable for storage in inputs_json.
    """
    return json.dumps(dataclasses.asdict(inputs))


def deserialize_inputs(json_str: str) -> FIInputs:
    """Deserialize a JSON string back to a FIInputs dataclass.

    Args:
        json_str: A JSON string previously produced by serialize_inputs.

    Returns:
        A FIInputs instance with all fields restored.
    """
    return FIInputs(**json.loads(json_str))


def serialize_results(result: SimulationResult) -> str:
    """Serialize a SimulationResult to a JSON string.

    Converts int percentile keys to strings (required by JSON) and ensures
    numpy arrays are represented as plain Python lists.

    Args:
        result: The SimulationResult instance to serialize.

    Returns:
        A JSON string suitable for storage in results_json.
    """
    payload = {
        "success_rate": result.success_rate,
        "n_simulations": result.n_simulations,
        "fi_number": result.fi_number,
        "ages": result.ages,
        # JSON requires string keys; int keys are restored on deserialisation.
        "percentile_bands": {str(k): v for k, v in result.percentile_bands.items()},
        "inputs_snapshot": result.inputs_snapshot,
    }
    return json.dumps(payload)


def deserialize_results(json_str: str) -> SimulationResult:
    """Deserialize a JSON string back to a SimulationResult.

    Converts string percentile keys back to ints and list values back to
    the expected types.

    Args:
        json_str: A JSON string previously produced by serialize_results.

    Returns:
        A SimulationResult instance with all fields restored.
    """
    data = json.loads(json_str)
    percentile_bands = {int(k): v for k, v in data["percentile_bands"].items()}
    return SimulationResult(
        success_rate=data["success_rate"],
        n_simulations=data["n_simulations"],
        fi_number=data["fi_number"],
        ages=data["ages"],
        percentile_bands=percentile_bands,
        inputs_snapshot=data.get("inputs_snapshot", {}),
    )
