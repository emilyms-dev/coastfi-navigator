"""CRUD tests — Phase 3.

Integration tests for app/db/crud.py using a test database.

SQLite in-memory is used for speed and CI portability. Trade-off: SQLite does
not enforce all PostgreSQL constraints (e.g. it has looser type coercion) and
lacks some server functions (e.g. gen_random_uuid()). All share-token logic
is handled in Python (uuid.uuid4()), so portability is not a concern here.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.crud as crud_module
from app.db.models import Base
from app.engine.calculator import FIInputs
from app.engine.monte_carlo import run_simulation

# ── Test fixture ──────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory SQLite database for each test.

    Uses StaticPool so the same in-memory DB is shared across connections
    within a test. All tables are created before the test and dropped after,
    giving each test function a clean slate.

    The fixture patches crud_module.Session so that all CRUD functions use
    this test session instead of the production Postgres session.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    # Redirect the module-level Session used by crud.py to the test session.
    original_session = crud_module.Session
    crud_module.Session = TestSession
    yield TestSession
    crud_module.Session = original_session
    Base.metadata.drop_all(engine)
    engine.dispose()


# ── Helpers ───────────────────────────────────────────────────────────


def _make_inputs(**overrides) -> FIInputs:
    """Return a valid FIInputs with sensible defaults, optionally overridden."""
    defaults = dict(
        current_age=30,
        retirement_age=65,
        current_portfolio=150_000.0,
        monthly_contribution=2_000.0,
        annual_spending=60_000.0,
        nominal_return_rate=0.07,
        inflation_rate=0.03,
    )
    return FIInputs(**{**defaults, **overrides})


# ── User tests ────────────────────────────────────────────────────────


def test_create_user_success(db_session) -> None:
    user = crud_module.create_user("alice@example.com", "hashed_pw")
    assert user.id is not None
    assert user.email == "alice@example.com"


def test_create_user_duplicate_email(db_session) -> None:
    crud_module.create_user("bob@example.com", "hash1")
    with pytest.raises(ValueError, match="already exists"):
        crud_module.create_user("bob@example.com", "hash2")


def test_get_user_by_email_found(db_session) -> None:
    created = crud_module.create_user("carol@example.com", "hash")
    found = crud_module.get_user_by_email("carol@example.com")
    assert found is not None
    assert found.id == created.id


def test_get_user_by_email_not_found(db_session) -> None:
    result = crud_module.get_user_by_email("nobody@example.com")
    assert result is None


def test_get_user_by_id_found(db_session) -> None:
    created = crud_module.create_user("dave@example.com", "hash")
    found = crud_module.get_user_by_id(created.id)
    assert found is not None
    assert found.email == "dave@example.com"


def test_get_user_by_id_not_found(db_session) -> None:
    assert crud_module.get_user_by_id(99999) is None


# ── Scenario tests ────────────────────────────────────────────────────


def test_create_scenario_and_retrieve(db_session) -> None:
    user = crud_module.create_user("eve@example.com", "hash")
    crud_module.create_scenario(user.id, "Conservative Plan")
    scenarios = crud_module.get_scenarios_for_user(user.id)
    assert len(scenarios) == 1
    assert scenarios[0].name == "Conservative Plan"


def test_get_scenarios_for_user_ordered_desc(db_session) -> None:
    user = crud_module.create_user("frank@example.com", "hash")
    s1 = crud_module.create_scenario(user.id, "First")
    s2 = crud_module.create_scenario(user.id, "Second")
    scenarios = crud_module.get_scenarios_for_user(user.id)
    # Newest first
    assert scenarios[0].id == s2.id
    assert scenarios[1].id == s1.id


def test_get_scenario_ownership_enforced(db_session) -> None:
    u1 = crud_module.create_user("user1@example.com", "hash")
    u2 = crud_module.create_user("user2@example.com", "hash")
    scenario = crud_module.create_scenario(u1.id, "Private Plan")
    # Owner can see it
    assert crud_module.get_scenario_by_id(scenario.id, u1.id) is not None
    # Other user cannot see it
    assert crud_module.get_scenario_by_id(scenario.id, u2.id) is None


def test_delete_scenario_removes_snapshots(db_session) -> None:
    user = crud_module.create_user("grace@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Plan to Delete")
    inputs_json = crud_module.serialize_inputs(_make_inputs())
    crud_module.save_snapshot(scenario.id, inputs_json, user.id)
    crud_module.save_snapshot(scenario.id, inputs_json, user.id)

    deleted = crud_module.delete_scenario(scenario.id, user.id)
    assert deleted is True
    # Scenario is gone
    assert crud_module.get_scenario_by_id(scenario.id, user.id) is None
    # Snapshots are gone (cascade + ownership join returns [])
    assert crud_module.get_snapshots_for_scenario(scenario.id, user.id) == []


def test_delete_scenario_wrong_user(db_session) -> None:
    u1 = crud_module.create_user("henry@example.com", "hash")
    u2 = crud_module.create_user("iris@example.com", "hash")
    scenario = crud_module.create_scenario(u1.id, "Plan")
    result = crud_module.delete_scenario(scenario.id, u2.id)
    assert result is False
    # Still exists for the owner
    assert crud_module.get_scenario_by_id(scenario.id, u1.id) is not None


# ── Share token tests ─────────────────────────────────────────────────


def test_generate_share_token_idempotent(db_session) -> None:
    user = crud_module.create_user("jack@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Share Me")
    token1 = crud_module.generate_share_token(scenario.id, user.id)
    token2 = crud_module.generate_share_token(scenario.id, user.id)
    assert token1 == token2
    assert len(token1) == 36  # UUID4 string length


def test_generate_share_token_wrong_user_raises(db_session) -> None:
    u1 = crud_module.create_user("kate@example.com", "hash")
    u2 = crud_module.create_user("liam@example.com", "hash")
    scenario = crud_module.create_scenario(u1.id, "Plan")
    with pytest.raises(ValueError, match="not found or not owned"):
        crud_module.generate_share_token(scenario.id, u2.id)


def test_get_scenario_by_share_token(db_session) -> None:
    user = crud_module.create_user("mia@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Shareable Plan")
    token = crud_module.generate_share_token(scenario.id, user.id)
    found = crud_module.get_scenario_by_share_token(token)
    assert found is not None
    assert found.id == scenario.id


def test_get_scenario_by_share_token_invalid(db_session) -> None:
    result = crud_module.get_scenario_by_share_token("not-a-real-token")
    assert result is None


# ── Snapshot tests ────────────────────────────────────────────────────


def test_save_snapshot_creates_new_row(db_session) -> None:
    user = crud_module.create_user("noah@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Plan")
    inputs_json = crud_module.serialize_inputs(_make_inputs())

    snap1 = crud_module.save_snapshot(scenario.id, inputs_json, user.id)
    snap2 = crud_module.save_snapshot(scenario.id, inputs_json, user.id)

    assert snap1.id != snap2.id
    assert snap1.version == 1
    assert snap2.version == 2


def test_snapshot_version_increments(db_session) -> None:
    user = crud_module.create_user("olivia@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Plan")
    inputs_json = crud_module.serialize_inputs(_make_inputs())

    versions = [
        crud_module.save_snapshot(scenario.id, inputs_json, user.id).version
        for _ in range(3)
    ]
    assert versions == [1, 2, 3]


def test_get_latest_snapshot(db_session) -> None:
    user = crud_module.create_user("peter@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Plan")
    inputs_json = crud_module.serialize_inputs(_make_inputs())

    for _ in range(3):
        crud_module.save_snapshot(scenario.id, inputs_json, user.id)

    latest = crud_module.get_latest_snapshot(scenario.id, user.id)
    assert latest is not None
    assert latest.version == 3


def test_get_latest_snapshot_none_when_empty(db_session) -> None:
    user = crud_module.create_user("quinn@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Empty Plan")
    assert crud_module.get_latest_snapshot(scenario.id, user.id) is None


def test_get_snapshots_for_scenario_limit(db_session) -> None:
    user = crud_module.create_user("rachel@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Plan")
    inputs_json = crud_module.serialize_inputs(_make_inputs())

    for _ in range(5):
        crud_module.save_snapshot(scenario.id, inputs_json, user.id)

    snapshots = crud_module.get_snapshots_for_scenario(scenario.id, user.id, limit=3)
    assert len(snapshots) == 3


def test_snapshot_results_json_optional(db_session) -> None:
    user = crud_module.create_user("sam@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Plan")
    inputs_json = crud_module.serialize_inputs(_make_inputs())

    snap = crud_module.save_snapshot(
        scenario.id, inputs_json, user.id, results_json=None
    )
    assert snap.results_json is None


def test_save_snapshot_wrong_user_raises(db_session) -> None:
    u1 = crud_module.create_user("tara@example.com", "hash")
    u2 = crud_module.create_user("ulric@example.com", "hash")
    scenario = crud_module.create_scenario(u1.id, "Plan")
    inputs_json = crud_module.serialize_inputs(_make_inputs())
    with pytest.raises(ValueError, match="not found or not owned"):
        crud_module.save_snapshot(scenario.id, inputs_json, u2.id)


def test_get_snapshots_wrong_user_returns_empty(db_session) -> None:
    u1 = crud_module.create_user("vera@example.com", "hash")
    u2 = crud_module.create_user("will@example.com", "hash")
    scenario = crud_module.create_scenario(u1.id, "Plan")
    inputs_json = crud_module.serialize_inputs(_make_inputs())
    crud_module.save_snapshot(scenario.id, inputs_json, u1.id)
    assert crud_module.get_snapshots_for_scenario(scenario.id, u2.id) == []


def test_get_latest_snapshot_wrong_user_returns_none(db_session) -> None:
    u1 = crud_module.create_user("xena@example.com", "hash")
    u2 = crud_module.create_user("yuri@example.com", "hash")
    scenario = crud_module.create_scenario(u1.id, "Plan")
    inputs_json = crud_module.serialize_inputs(_make_inputs())
    crud_module.save_snapshot(scenario.id, inputs_json, u1.id)
    assert crud_module.get_latest_snapshot(scenario.id, u2.id) is None


# ── Serialization round-trip tests ───────────────────────────────────


def test_serialization_round_trip(db_session) -> None:
    inputs = _make_inputs()
    json_str = crud_module.serialize_inputs(inputs)
    restored = crud_module.deserialize_inputs(json_str)

    assert restored.current_age == inputs.current_age
    assert restored.retirement_age == inputs.retirement_age
    assert restored.current_portfolio == inputs.current_portfolio
    assert restored.monthly_contribution == inputs.monthly_contribution
    assert restored.annual_spending == inputs.annual_spending
    assert restored.nominal_return_rate == inputs.nominal_return_rate
    assert restored.inflation_rate == inputs.inflation_rate
    assert restored.lean_multiplier == inputs.lean_multiplier
    assert restored.barista_income == inputs.barista_income


def test_results_serialization_round_trip(db_session) -> None:
    inputs = _make_inputs()
    result = run_simulation(inputs, n_simulations=100, rng_seed=42)

    json_str = crud_module.serialize_results(result)
    restored = crud_module.deserialize_results(json_str)

    assert abs(restored.success_rate - result.success_rate) < 1e-9
    assert restored.n_simulations == result.n_simulations
    assert restored.fi_number == result.fi_number
    assert restored.ages == result.ages
    # Percentile keys must be ints after deserialisation (not strings)
    assert all(isinstance(k, int) for k in restored.percentile_bands.keys())
    assert set(restored.percentile_bands.keys()) == {10, 25, 50, 75, 90}
    for pct in (10, 25, 50, 75, 90):
        assert len(restored.percentile_bands[pct]) == len(result.percentile_bands[pct])


# ── Model __repr__ tests (Phase 3 N3) ────────────────────────────────


def test_user_repr(db_session) -> None:
    user = crud_module.create_user("repr_user@example.com", "hash")
    r = repr(user)
    assert "User(" in r
    assert "repr_user@example.com" in r


def test_scenario_repr(db_session) -> None:
    user = crud_module.create_user("repr_scenario@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Repr Test Plan")
    r = repr(scenario)
    assert "Scenario(" in r
    assert "Repr Test Plan" in r


def test_snapshot_repr(db_session) -> None:
    user = crud_module.create_user("repr_snap@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Plan")
    inputs_json = crud_module.serialize_inputs(_make_inputs())
    snap = crud_module.save_snapshot(scenario.id, inputs_json, user.id)
    r = repr(snap)
    assert "ScenarioSnapshot(" in r
    assert str(snap.version) in r


# ── Detached-instance attribute test (Phase 3 N4) ────────────────────


def test_detached_scenario_attributes_accessible(db_session) -> None:
    """Eagerly-loaded .snapshots must be accessible after the session closes.

    get_scenarios_for_user uses selectinload — this confirms that accessing
    .snapshots on a detached Scenario does not raise DetachedInstanceError,
    i.e., the eager-load assumption holds against the test DB.
    """
    user = crud_module.create_user("detach@example.com", "hash")
    scenario = crud_module.create_scenario(user.id, "Detach Plan")
    inputs_json = crud_module.serialize_inputs(_make_inputs())
    crud_module.save_snapshot(scenario.id, inputs_json, user.id)

    # Objects returned by get_scenarios_for_user are detached (session closed).
    scenarios = crud_module.get_scenarios_for_user(user.id)
    assert len(scenarios) == 1
    detached = scenarios[0]
    # Accessing the relationship must not raise DetachedInstanceError.
    assert len(detached.snapshots) == 1
    assert detached.snapshots[0].version == 1


# ── Serialization key-set tests (Phase 3 S1) ─────────────────────────


def test_serialize_inputs_key_set(db_session) -> None:
    inputs = _make_inputs()
    payload = json.loads(crud_module.serialize_inputs(inputs))
    assert set(payload.keys()) == {
        "current_age",
        "retirement_age",
        "current_portfolio",
        "monthly_contribution",
        "annual_spending",
        "nominal_return_rate",
        "inflation_rate",
        "lean_multiplier",
        "barista_income",
    }


def test_serialize_results_key_set(db_session) -> None:
    inputs = _make_inputs()
    result = run_simulation(inputs, n_simulations=100, rng_seed=42)
    payload = json.loads(crud_module.serialize_results(result))
    assert set(payload.keys()) == {
        "success_rate",
        "n_simulations",
        "fi_number",
        "ages",
        "percentile_bands",
        "inputs_snapshot",
    }
