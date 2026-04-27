"""Demo data seed script.

Creates a demo user and three pre-populated scenarios so the app is
immediately usable after a fresh deployment. Safe to run multiple times —
idempotent via email check.

Usage (from the project root inside the container):
    python scripts/seed_demo.py

Or via podman-compose:
    podman-compose exec app python scripts/seed_demo.py
"""

from __future__ import annotations

import logging
import os
import sys

import bcrypt
from dotenv import load_dotenv

load_dotenv()

# ── Path setup ────────────────────────────────────────────────────────────────
# Ensure the project root is on sys.path so `app.*` imports resolve
# whether this script is run from the root or the scripts/ directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Imports after path setup so app.* is importable.
from app.db import crud  # noqa: E402
from app.engine.calculator import FIInputs  # noqa: E402
from app.engine.monte_carlo import run_simulation  # noqa: E402

# ── Demo user credentials ──────────────────────────────────────────────────────
# These are intentionally public test credentials for local development and
# demos only. Do not run this script against a production database.

DEMO_EMAIL = "demo@coastfi.example"
DEMO_PASSWORD = "demo1234"

# ── Scenario definitions ───────────────────────────────────────────────────────

# Each entry is (scenario_name, FIInputs kwargs).
# Values are chosen to demonstrate different milestone states:
#   1. "Conservative Plan"  — modest returns, longer runway
#   2. "Aggressive Growth"  — higher return assumption, shorter horizon
#   3. "Barista FI Track"   — part-time income offsets expenses

_SCENARIOS: list[tuple[str, dict]] = [
    (
        "Conservative Plan",
        dict(
            current_age=30,
            retirement_age=65,
            current_portfolio=50_000.0,
            monthly_contribution=1_500.0,
            annual_spending=55_000.0,
            nominal_return_rate=0.06,
            inflation_rate=0.03,
            barista_income=0.0,
        ),
    ),
    (
        "Aggressive Growth",
        dict(
            current_age=28,
            retirement_age=55,
            current_portfolio=120_000.0,
            monthly_contribution=3_000.0,
            annual_spending=70_000.0,
            nominal_return_rate=0.08,
            inflation_rate=0.03,
            barista_income=0.0,
        ),
    ),
    (
        "Barista FI Track",
        dict(
            current_age=35,
            retirement_age=55,
            current_portfolio=80_000.0,
            monthly_contribution=1_000.0,
            annual_spending=50_000.0,
            nominal_return_rate=0.07,
            inflation_rate=0.03,
            barista_income=20_000.0,
        ),
    ),
]


# ── Seed logic ─────────────────────────────────────────────────────────────────


def seed() -> None:
    """Create demo user and scenarios; idempotent."""

    # ── User ──────────────────────────────────────────────────────────────────
    existing_user = crud.get_user_by_email(DEMO_EMAIL)
    if existing_user is not None:
        logger.info(
            "Demo user already exists (id=%d) — skipping user creation.",
            existing_user.id,
        )
        user = existing_user
    else:
        pw_hash = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt()).decode()
        user = crud.create_user(DEMO_EMAIL, pw_hash)
        logger.info("Created demo user: %s (id=%d)", DEMO_EMAIL, user.id)

    # ── Scenarios ─────────────────────────────────────────────────────────────
    existing_scenarios = crud.get_scenarios_for_user(user.id)
    existing_names = {s.name for s in existing_scenarios}

    for scenario_name, inputs_kwargs in _SCENARIOS:
        if scenario_name in existing_names:
            logger.info("Scenario %r already exists — skipping.", scenario_name)
            continue

        scenario = crud.create_scenario(user.id, scenario_name)
        fi_inputs = FIInputs(**inputs_kwargs)

        sim_result = run_simulation(fi_inputs, n_simulations=1000, rng_seed=42)
        inputs_json = crud.serialize_inputs(fi_inputs)
        results_json = crud.serialize_results(sim_result)

        crud.save_snapshot(
            scenario_id=scenario.id,
            inputs_json=inputs_json,
            user_id=user.id,
            results_json=results_json,
        )
        logger.info(
            "Created scenario %r (id=%d, success_rate=%.1f%%)",
            scenario_name,
            scenario.id,
            sim_result.success_rate * 100,
        )

    logger.info(
        "Seed complete. Log in with %s / %s", DEMO_EMAIL, DEMO_PASSWORD
    )


if __name__ == "__main__":
    seed()
