"""Edge case tests for SQLAlchemy adapter flush/commit timing semantics.

Verifies tenant enforcement timing relative to:

- ``Session.flush()`` (explicit flush).
- Autoflush (implicit flush before SELECT queries).
- ``Session.commit()`` (implicit flush during commit).
- Scope changes between ``add()`` and ``flush()``.
- ``Session.expunge()`` (instance no longer in session).

Materializes DR-025 (flush-time enforcement semantics).

Pattern: enforcement is event-driven; events fire at flush time
regardless of when ``add()`` was called. Adopters must ensure tenant
scope active throughout session operations, NOT just during instance
creation.

See also
--------

- ADR-0007 (event-based enforcement consequences).
- DR-021 (write enforcement via mapper events).
- DR-022 (read enforcement via session events).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tenantshield import TenantId, bind_tenant, tenant_scope
from tenantshield.adapters.sqlalchemy import tenant_aware
from tenantshield.exceptions import MissingTenantContextError

if TYPE_CHECKING:
    from collections.abc import Generator


class _Base(DeclarativeBase):
    """Test-local declarative base."""


@tenant_aware
class _Invoice(_Base):
    __tablename__ = "test_invoice_flush_timing"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()
    amount: Mapped[int] = mapped_column()


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:")
    _Base.metadata.create_all(engine)
    try:
        with Session(engine) as s:
            yield s
    finally:
        engine.dispose()


class TestFlushTimingEnforcement:
    """Verify enforcement fires at flush time, not at add time."""

    def test_scope_exit_before_flush_raises_at_flush(self, session: Session) -> None:
        """Scope exiting before flush raises MissingTenantContextError at flush.

        Enforcement is event-driven; event fires at flush time. If
        scope is no longer active, MissingTenantContextError raises.

        DR-025: adopters must keep scope active through flush.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(amount=100))

        with pytest.raises(MissingTenantContextError) as exc_info:
            session.flush()

        assert "before_insert" in exc_info.value.operation

    def test_scope_change_between_add_and_flush_uses_flush_time_scope(
        self, session: Session
    ) -> None:
        """Scope changes between add() and flush() use scope-at-flush.

        Auto-injection reflects flush-time scope, not add-time scope.
        Pattern documented in DR-025.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(amount=100))

        with tenant_scope(bind_tenant(TenantId("globex"))):
            session.flush()
            session.commit()

        rows = session.execute(text("SELECT tenant_id FROM test_invoice_flush_timing")).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "globex"


class TestAutoflushBehavior:
    """Verify autoflush triggers events correctly."""

    def test_select_triggers_autoflush_and_event_firing(self, session: Session) -> None:
        """SELECT triggers autoflush; before_insert fires before the SELECT.

        Adopters relying on autoflush get the same enforcement as
        explicit flush().
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(amount=100))
            rows = session.execute(select(_Invoice)).scalars().all()
            assert len(rows) == 1
            assert rows[0].tenant_id == "acme"

    def test_autoflush_without_scope_raises(self, session: Session) -> None:
        """Autoflush without active scope raises MissingTenantContextError.

        Same enforcement timing applies whether flush is explicit
        or auto-triggered.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(amount=100))

        with pytest.raises(MissingTenantContextError):
            session.execute(select(_Invoice)).scalars().all()


class TestCommitTimingEnforcement:
    """Verify commit triggers implicit flush + events."""

    def test_commit_without_explicit_flush_fires_events(self, session: Session) -> None:
        """commit() with pending changes triggers implicit flush + events.

        Adopters not calling explicit flush() still get enforcement
        via commit's implicit flush.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(amount=100))
            session.add(_Invoice(amount=200))
            session.commit()

        rows = session.execute(text("SELECT tenant_id FROM test_invoice_flush_timing")).fetchall()
        assert len(rows) == 2
        assert all(r[0] == "acme" for r in rows)

    def test_commit_outside_scope_with_pending_adds_raises(self, session: Session) -> None:
        """commit() outside scope with pending adds raises during implicit flush.

        Mirrors flush() outside scope behavior; commit triggers flush.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(amount=100))

        with pytest.raises(MissingTenantContextError):
            session.commit()


class TestExpungeBehavior:
    """Verify expunged instances don't fire events."""

    def test_expunged_instance_does_not_fire_events(self, session: Session) -> None:
        """Expunged instances no longer in session; events don't fire.

        Standard SA behavior; documented for completeness.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            inv = _Invoice(amount=100)
            session.add(inv)
            session.expunge(inv)
            session.flush()
            session.commit()

        count = session.execute(text("SELECT COUNT(*) FROM test_invoice_flush_timing")).scalar_one()
        assert count == 0
