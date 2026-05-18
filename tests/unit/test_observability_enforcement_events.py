"""Unit tests for enforcement events emission (Sub-fase 5B.3).

Verifies 4 enforcement events emitted at canonical decision sites in
``tenantshield.adapters.sqlalchemy.events``:

- ``tenant.write.injected`` (DEBUG) -- ``before_insert`` auto-inject path.
- ``tenant.write.blocked`` (WARNING) -- cross-tenant write (INSERT/UPDATE/DELETE).
- ``tenant.read.filtered`` (DEBUG) -- ``do_orm_execute`` filter applied to
  tenant-aware entity.
- ``tenant.read.fallthrough`` (DEBUG) -- ``do_orm_execute`` invoked without
  active tenant scope (no filter applied; per DR-022 fall-through semantics).

Phase 3A event-based enforcement architecture preserved; emission additive.
Phase 4A AsyncSession compatibility automatic via ``sync_session_class``
event delegation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from structlog.testing import capture_logs

from tenantshield import TenantId, bind_tenant, tenant_scope
from tenantshield.adapters.sqlalchemy import tenant_aware
from tenantshield.exceptions import CrossTenantAccessError
from tenantshield.observability import configure
from tenantshield.observability.events import (
    EVENT_READ_FALLTHROUGH,
    EVENT_READ_FILTERED,
    EVENT_WRITE_BLOCKED,
    EVENT_WRITE_INJECTED,
)

if TYPE_CHECKING:
    from collections.abc import Generator


class _Base(DeclarativeBase):
    """Test-local declarative base."""


@tenant_aware
class _Widget(_Base):
    __tablename__ = "test_widget_obs"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """In-memory SQLite session per test."""
    engine = create_engine("sqlite:///:memory:")
    _Base.metadata.create_all(engine)
    try:
        with Session(engine) as s:
            yield s
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _reset_observability() -> Generator[None, None, None]:
    configure(emit_events=False)
    yield
    configure(emit_events=False)


def _attempt_cross_tenant_update(session: Session, source_tenant: str, attack_tenant: str) -> None:
    """Helper: insert under ``source_tenant`` then UPDATE under ``attack_tenant``."""
    with tenant_scope(bind_tenant(TenantId(source_tenant))):
        widget = _Widget()
        session.add(widget)
        session.flush()
        session.commit()
    with tenant_scope(bind_tenant(TenantId(attack_tenant))):
        widget.tenant_id = source_tenant
        session.flush()


def _attempt_cross_tenant_delete(session: Session, source_tenant: str, attack_tenant: str) -> None:
    """Helper: insert under ``source_tenant`` then DELETE under ``attack_tenant``."""
    with tenant_scope(bind_tenant(TenantId(source_tenant))):
        widget = _Widget()
        session.add(widget)
        session.flush()
        session.commit()
    with tenant_scope(bind_tenant(TenantId(attack_tenant))):
        session.delete(widget)
        session.flush()


class TestWriteInjectedEvent:
    """Verify ``EVENT_WRITE_INJECTED`` emitted on auto-inject path."""

    def test_emitted_on_insert_auto_inject(self, session: Session) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, tenant_scope(bind_tenant(TenantId("acme"))):
            widget = _Widget()
            session.add(widget)
            session.flush()

        injected = [e for e in logs if e.get("event") == EVENT_WRITE_INJECTED]
        assert len(injected) == 1
        assert injected[0]["tenant_id"] == "acme"
        assert injected[0]["operation"] == "before_insert"
        assert "_Widget" in injected[0]["model_class"]

    def test_not_emitted_when_explicit_match(self, session: Session) -> None:
        """If tenant_id explicitly set + matches scope: no inject emission."""
        configure(emit_events=True)
        with capture_logs() as logs, tenant_scope(bind_tenant(TenantId("acme"))):
            widget = _Widget(tenant_id="acme")
            session.add(widget)
            session.flush()

        injected = [e for e in logs if e.get("event") == EVENT_WRITE_INJECTED]
        assert len(injected) == 0

    def test_not_emitted_when_disabled(self, session: Session) -> None:
        configure(emit_events=False)
        with capture_logs() as logs, tenant_scope(bind_tenant(TenantId("acme"))):
            widget = _Widget()
            session.add(widget)
            session.flush()

        injected = [e for e in logs if e.get("event") == EVENT_WRITE_INJECTED]
        assert len(injected) == 0


class TestWriteBlockedEvent:
    """Verify ``EVENT_WRITE_BLOCKED`` emitted across INSERT/UPDATE/DELETE paths."""

    def test_emitted_on_insert_mismatch(self, session: Session) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, tenant_scope(bind_tenant(TenantId("acme"))):
            widget = _Widget(tenant_id="globex")
            session.add(widget)
            with pytest.raises(CrossTenantAccessError):
                session.flush()

        blocked = [e for e in logs if e.get("event") == EVENT_WRITE_BLOCKED]
        assert len(blocked) == 1
        assert blocked[0]["tenant_id"] == "acme"
        assert blocked[0]["attempted_tenant_id"] == "globex"
        assert blocked[0]["operation"] == "before_insert"

    def test_emitted_on_update_mismatch(self, session: Session) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, pytest.raises(CrossTenantAccessError):
            _attempt_cross_tenant_update(session, "acme", "globex")

        blocked = [
            e
            for e in logs
            if e.get("event") == EVENT_WRITE_BLOCKED and e.get("operation") == "before_update"
        ]
        assert len(blocked) == 1
        assert blocked[0]["tenant_id"] == "globex"
        assert blocked[0]["attempted_tenant_id"] == "acme"

    def test_emitted_on_delete_mismatch(self, session: Session) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, pytest.raises(CrossTenantAccessError):
            _attempt_cross_tenant_delete(session, "acme", "globex")

        blocked = [
            e
            for e in logs
            if e.get("event") == EVENT_WRITE_BLOCKED and e.get("operation") == "before_delete"
        ]
        assert len(blocked) == 1
        assert blocked[0]["tenant_id"] == "globex"
        assert blocked[0]["attempted_tenant_id"] == "acme"

    def test_not_emitted_when_disabled(self, session: Session) -> None:
        configure(emit_events=False)
        with capture_logs() as logs, tenant_scope(bind_tenant(TenantId("acme"))):
            widget = _Widget(tenant_id="globex")
            session.add(widget)
            with pytest.raises(CrossTenantAccessError):
                session.flush()

        blocked = [e for e in logs if e.get("event") == EVENT_WRITE_BLOCKED]
        assert len(blocked) == 0


class TestReadFilteredEvent:
    """Verify ``EVENT_READ_FILTERED`` emitted when ``do_orm_execute`` applies filter."""

    def test_emitted_on_select_under_scope(self, session: Session) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, tenant_scope(bind_tenant(TenantId("acme"))):
            session.execute(select(_Widget))

        filtered = [e for e in logs if e.get("event") == EVENT_READ_FILTERED]
        assert len(filtered) == 1
        assert filtered[0]["tenant_id"] == "acme"
        assert "_Widget" in filtered[0]["model_class"]

    def test_not_emitted_when_disabled(self, session: Session) -> None:
        configure(emit_events=False)
        with capture_logs() as logs, tenant_scope(bind_tenant(TenantId("acme"))):
            session.execute(select(_Widget))

        filtered = [e for e in logs if e.get("event") == EVENT_READ_FILTERED]
        assert len(filtered) == 0


class TestReadFallthroughEvent:
    """Verify ``EVENT_READ_FALLTHROUGH`` emitted when SELECT runs without scope."""

    def test_emitted_without_scope(self, session: Session) -> None:
        configure(emit_events=True)
        with capture_logs() as logs:
            session.execute(select(_Widget))

        fallthrough = [e for e in logs if e.get("event") == EVENT_READ_FALLTHROUGH]
        assert len(fallthrough) == 1
        assert fallthrough[0]["operation"] == "do_orm_execute"

    def test_not_emitted_when_disabled(self, session: Session) -> None:
        configure(emit_events=False)
        with capture_logs() as logs:
            session.execute(select(_Widget))

        fallthrough = [e for e in logs if e.get("event") == EVENT_READ_FALLTHROUGH]
        assert len(fallthrough) == 0

    def test_not_emitted_under_scope(self, session: Session) -> None:
        """When scope is active, filter applies -- no fallthrough."""
        configure(emit_events=True)
        with capture_logs() as logs, tenant_scope(bind_tenant(TenantId("acme"))):
            session.execute(select(_Widget))

        fallthrough = [e for e in logs if e.get("event") == EVENT_READ_FALLTHROUGH]
        assert len(fallthrough) == 0
