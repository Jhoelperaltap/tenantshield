"""Unit tests for SQLAlchemy adapter event listeners (write enforcement).

Tests INSERT path enforcement via before_insert event listener.
UPDATE/DELETE coverage in Tarea 3A.4; read filtering in Tarea 3A.5.

Test patterns follow Phase 2 canonical:

    with tenant_scope(bind_tenant(TenantId("acme"))):
        ...

Match Django adapter test patterns for cross-adapter coherence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tenantshield import TenantId, bind_tenant, tenant_scope
from tenantshield.adapters.sqlalchemy import tenant_aware
from tenantshield.exceptions import CrossTenantAccessError, MissingTenantContextError

if TYPE_CHECKING:
    from collections.abc import Generator


class _Base(DeclarativeBase):
    """Test-local declarative base."""


@tenant_aware
class _Invoice(_Base):
    __tablename__ = "test_invoice_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()


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


class TestBeforeInsertEventListener:
    """Verify before_insert event enforcement on tenant-aware models."""

    def test_insert_without_scope_raises_missing_context(self, session: Session) -> None:
        invoice = _Invoice()
        session.add(invoice)
        with pytest.raises(MissingTenantContextError) as exc_info:
            session.flush()

        assert "before_insert" in exc_info.value.operation
        assert "_Invoice" in exc_info.value.operation

    def test_insert_with_scope_auto_injects_tenant_id(self, session: Session) -> None:
        with tenant_scope(bind_tenant(TenantId("acme"))):
            invoice = _Invoice()
            session.add(invoice)
            session.flush()
            assert invoice.tenant_id == "acme"
            session.commit()

    def test_insert_with_matching_explicit_tenant_id_succeeds(self, session: Session) -> None:
        with tenant_scope(bind_tenant(TenantId("acme"))):
            invoice = _Invoice(tenant_id="acme")
            session.add(invoice)
            session.flush()
            assert invoice.tenant_id == "acme"
            session.commit()

    def test_insert_with_mismatched_tenant_id_raises_cross_tenant_access(
        self, session: Session
    ) -> None:
        with tenant_scope(bind_tenant(TenantId("acme"))):
            invoice = _Invoice(tenant_id="globex")
            session.add(invoice)
            with pytest.raises(CrossTenantAccessError) as exc_info:
                session.flush()

            assert str(exc_info.value.tenant_id_expected) == "acme"
            assert str(exc_info.value.tenant_id_actual) == "globex"
            assert "_Invoice" in exc_info.value.model

    def test_insert_outside_then_inside_scope_separate_records(self, session: Session) -> None:
        invoice_no_scope = _Invoice()
        session.add(invoice_no_scope)
        with pytest.raises(MissingTenantContextError):
            session.flush()

        session.rollback()
        with tenant_scope(bind_tenant(TenantId("acme"))):
            invoice_with_scope = _Invoice()
            session.add(invoice_with_scope)
            session.flush()
            assert invoice_with_scope.tenant_id == "acme"
            session.commit()

    def test_multiple_inserts_in_same_scope_inject_same_tenant(self, session: Session) -> None:
        with tenant_scope(bind_tenant(TenantId("acme"))):
            inv_a = _Invoice()
            inv_b = _Invoice()
            session.add_all([inv_a, inv_b])
            session.flush()
            assert inv_a.tenant_id == "acme"
            assert inv_b.tenant_id == "acme"
            session.commit()

    def test_inserts_in_distinct_scopes_inject_correctly(self, session: Session) -> None:
        with tenant_scope(bind_tenant(TenantId("acme"))):
            inv_acme = _Invoice()
            session.add(inv_acme)
            session.flush()
            session.commit()

        with tenant_scope(bind_tenant(TenantId("globex"))):
            inv_globex = _Invoice()
            session.add(inv_globex)
            session.flush()
            session.commit()

        assert inv_acme.tenant_id == "acme"
        assert inv_globex.tenant_id == "globex"
