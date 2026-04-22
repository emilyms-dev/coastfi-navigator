"""SQLAlchemy ORM models — Phase 3.

Defines the database schema for users, scenarios, and related entities.
All models inherit from a shared declarative Base that Alembic uses for
autogenerate migrations.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models.

    Alembic's autogenerate reads ``Base.metadata`` to detect schema changes.
    All model classes must inherit from this class.
    """


class User(Base):
    """An authenticated user of the application.

    Attributes:
        id: Auto-incremented primary key.
        email: Unique login email address, indexed for fast lookup.
        password_hash: bcrypt-hashed password. Never the plaintext password.
        created_at: Timestamp set by the database on INSERT.
        updated_at: Timestamp updated by the database on every UPDATE.
        scenarios: All scenarios owned by this user.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    scenarios: Mapped[list[Scenario]] = relationship(
        "Scenario", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"


class Scenario(Base):
    """A named planning scenario belonging to a user.

    A scenario is a container for snapshots — it holds the name and share
    state. The actual saved inputs and results live in ScenarioSnapshot rows.
    Every save appends a new snapshot; scenarios themselves are not versioned.

    Attributes:
        id: Auto-incremented primary key.
        user_id: Foreign key to the owning User, indexed for fast user queries.
        name: User-defined label e.g. "Conservative Plan", "Early Retirement".
        share_token: UUID4 string set on first share request, null if not shared.
            Indexed for fast public share-link lookups.
        created_at: Timestamp set by the database on INSERT.
        user: The owning User.
        snapshots: All snapshots for this scenario, ordered by created_at.
    """

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(nullable=False)
    share_token: Mapped[str | None] = mapped_column(
        nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship("User", back_populates="scenarios")
    snapshots: Mapped[list[ScenarioSnapshot]] = relationship(
        "ScenarioSnapshot",
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioSnapshot.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"Scenario(id={self.id!r}, name={self.name!r}, "
            f"user_id={self.user_id!r})"
        )


class ScenarioSnapshot(Base):
    """An immutable point-in-time save of a scenario's inputs and results.

    Snapshots are append-only — they are created once and never modified.
    This preserves the user's full planning history and enables the
    "how your plan evolved" feature. The version field monotonically
    increases per scenario and is computed at save time in crud.py.

    Attributes:
        id: Auto-incremented primary key.
        scenario_id: Foreign key to the parent Scenario, indexed.
        version: 1-based version counter within the scenario. Computed by
            crud.save_snapshot() as MAX(version) + 1 for the scenario_id.
        inputs_json: JSON-serialized FIInputs (via dataclasses.asdict()).
        results_json: JSON-serialized SimulationResult. Nullable — users may
            save without having run a simulation.
        created_at: Timestamp set by the database on INSERT.
        scenario: The parent Scenario.
    """

    __tablename__ = "scenario_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(nullable=False)
    inputs_json: Mapped[str] = mapped_column(nullable=False)
    results_json: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    scenario: Mapped[Scenario] = relationship("Scenario", back_populates="snapshots")

    # Composite index on (scenario_id, version) speeds up the MAX(version)
    # query in save_snapshot() and ordered snapshot retrieval.
    __table_args__ = (
        Index("ix_scenario_snapshots_scenario_version", "scenario_id", "version"),
    )

    def __repr__(self) -> str:
        return (
            f"ScenarioSnapshot(id={self.id!r}, scenario_id={self.scenario_id!r}, "
            f"version={self.version!r})"
        )
