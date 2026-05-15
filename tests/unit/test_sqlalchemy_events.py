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
from sqlalchemy import create_engine, func, select, text
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


class _NonTenantData(_Base):
    """Non-tenant-aware model for edge-case coverage of do_orm_execute."""

    __tablename__ = "test_non_tenant_data"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[int] = mapped_column()


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


def _insert_seed_invoice(session: Session, tenant: str) -> int:
    """Insert a seed invoice within tenant scope; return its id.

    Helper for UPDATE / DELETE tests that need pre-existing rows.
    """
    with tenant_scope(bind_tenant(TenantId(tenant))):
        inv = _Invoice(tenant_id=tenant)
        session.add(inv)
        session.flush()
        inv_id = inv.id
        session.commit()
    return inv_id


class TestBeforeUpdateEventListener:
    """Verify before_update event enforcement on tenant-aware models."""

    def test_update_without_scope_raises_missing_context(self, session: Session) -> None:
        inv_id = _insert_seed_invoice(session, "acme")

        with Session(session.bind) as fresh:
            inv = fresh.get(_Invoice, inv_id)
            assert inv is not None
            inv.tenant_id = "acme"
            with pytest.raises(MissingTenantContextError) as exc_info:
                fresh.flush()

            assert "before_update" in exc_info.value.operation

    def test_update_in_matching_scope_succeeds(self, session: Session) -> None:
        inv_id = _insert_seed_invoice(session, "acme")

        with tenant_scope(bind_tenant(TenantId("acme"))), Session(session.bind) as fresh:
            inv = fresh.get(_Invoice, inv_id)
            assert inv is not None
            inv.tenant_id = "acme"
            fresh.flush()
            fresh.commit()

    def test_update_cross_tenant_raises(self, session: Session) -> None:
        inv_id = _insert_seed_invoice(session, "globex")

        # Load OUTSIDE scope so do_orm_execute does not filter the
        # globex row out. Modify INSIDE acme scope to trigger
        # before_update under a mismatching context.
        with Session(session.bind) as fresh:
            inv = fresh.get(_Invoice, inv_id)
            assert inv is not None
            with tenant_scope(bind_tenant(TenantId("acme"))):
                inv.tenant_id = "globex"
                with pytest.raises(CrossTenantAccessError) as exc_info:
                    fresh.flush()

                assert str(exc_info.value.tenant_id_expected) == "acme"
                assert str(exc_info.value.tenant_id_actual) == "globex"

    def test_update_with_empty_tenant_id_raises_cross_tenant(self, session: Session) -> None:
        inv_id = _insert_seed_invoice(session, "acme")

        with tenant_scope(bind_tenant(TenantId("acme"))), Session(session.bind) as fresh:
            inv = fresh.get(_Invoice, inv_id)
            assert inv is not None
            inv.tenant_id = ""
            with pytest.raises(CrossTenantAccessError) as exc_info:
                fresh.flush()

            assert exc_info.value.tenant_id_actual is None
            assert "before_update" in exc_info.value.operation


class TestBeforeDeleteEventListener:
    """Verify before_delete event enforcement on tenant-aware models."""

    def test_delete_without_scope_raises_missing_context(self, session: Session) -> None:
        inv_id = _insert_seed_invoice(session, "acme")

        with Session(session.bind) as fresh:
            inv = fresh.get(_Invoice, inv_id)
            assert inv is not None
            fresh.delete(inv)
            with pytest.raises(MissingTenantContextError) as exc_info:
                fresh.flush()

            assert "before_delete" in exc_info.value.operation

    def test_delete_in_matching_scope_succeeds(self, session: Session) -> None:
        inv_id = _insert_seed_invoice(session, "acme")

        with tenant_scope(bind_tenant(TenantId("acme"))), Session(session.bind) as fresh:
            inv = fresh.get(_Invoice, inv_id)
            assert inv is not None
            fresh.delete(inv)
            fresh.flush()
            fresh.commit()
            still_there = fresh.get(_Invoice, inv_id)
            assert still_there is None

    def test_delete_cross_tenant_raises(self, session: Session) -> None:
        inv_id = _insert_seed_invoice(session, "globex")

        # Load OUTSIDE scope to bypass read filter; delete INSIDE acme
        # scope to trigger before_delete under mismatching context.
        with Session(session.bind) as fresh:
            inv = fresh.get(_Invoice, inv_id)
            assert inv is not None
            with tenant_scope(bind_tenant(TenantId("acme"))):
                fresh.delete(inv)
                with pytest.raises(CrossTenantAccessError) as exc_info:
                    fresh.flush()

                assert str(exc_info.value.tenant_id_expected) == "acme"
                assert str(exc_info.value.tenant_id_actual) == "globex"

    def test_delete_with_empty_tenant_id_raises_cross_tenant(self, session: Session) -> None:
        inv_id = _insert_seed_invoice(session, "acme")

        with tenant_scope(bind_tenant(TenantId("acme"))), Session(session.bind) as fresh:
            inv = fresh.get(_Invoice, inv_id)
            assert inv is not None
            inv.tenant_id = ""
            fresh.delete(inv)
            with pytest.raises(CrossTenantAccessError) as exc_info:
                fresh.flush()

            assert exc_info.value.tenant_id_actual is None
            assert "before_delete" in exc_info.value.operation


class TestDoOrmExecuteEventListener:
    """Verify do_orm_execute event filters reads on tenant-aware models."""

    def _seed_invoices(self, session: Session) -> None:
        """Helper: seed 2 acme invoices + 1 globex invoice."""
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(tenant_id="acme"))
            session.add(_Invoice(tenant_id="acme"))
            session.commit()
        with tenant_scope(bind_tenant(TenantId("globex"))):
            session.add(_Invoice(tenant_id="globex"))
            session.commit()

    def test_select_within_scope_returns_only_scope_rows(self, session: Session) -> None:
        self._seed_invoices(session)

        with tenant_scope(bind_tenant(TenantId("acme"))), Session(session.bind) as fresh:
            rows = fresh.execute(select(_Invoice)).scalars().all()
            assert len(rows) == 2
            assert all(r.tenant_id == "acme" for r in rows)

    def test_select_within_other_scope_returns_only_other_scope_rows(
        self, session: Session
    ) -> None:
        self._seed_invoices(session)

        with tenant_scope(bind_tenant(TenantId("globex"))), Session(session.bind) as fresh:
            rows = fresh.execute(select(_Invoice)).scalars().all()
            assert len(rows) == 1
            assert rows[0].tenant_id == "globex"

    def test_select_without_scope_returns_all_rows(self, session: Session) -> None:
        # Fall-through behavior: no active scope, no filtering applied.
        # Stricter behavior available via middleware in Sub-fase 3B.
        self._seed_invoices(session)

        with Session(session.bind) as fresh:
            rows = fresh.execute(select(_Invoice)).scalars().all()
            assert len(rows) == 3

    def test_filtered_query_with_where_combines_with_tenant_filter(self, session: Session) -> None:
        self._seed_invoices(session)

        with tenant_scope(bind_tenant(TenantId("acme"))), Session(session.bind) as fresh:
            stmt = select(_Invoice).where(_Invoice.id >= 1)
            rows = fresh.execute(stmt).scalars().all()
            assert len(rows) == 2
            assert all(r.tenant_id == "acme" for r in rows)

    def test_select_non_tenant_aware_model_passes_through(self, session: Session) -> None:
        """Non-tenant-aware model: do_orm_execute skips filter injection."""
        session.add(_NonTenantData(value=42))
        session.add(_NonTenantData(value=99))
        session.commit()

        with tenant_scope(bind_tenant(TenantId("acme"))), Session(session.bind) as fresh:
            rows = fresh.execute(select(_NonTenantData)).scalars().all()
            assert len(rows) == 2

    def test_raw_sql_passes_through_without_filter_injection(self, session: Session) -> None:
        """Raw SQL (text()) is not an ORM statement; handler short-circuits."""

        with tenant_scope(bind_tenant(TenantId("acme"))):
            result = session.execute(text("SELECT 1 AS one"))
            assert list(result) == [(1,)]

    def test_bare_function_in_select_skips_entity_none_entries(self, session: Session) -> None:
        """SELECT with bare function/literal yields entity=None in column_descriptions."""

        self._seed_invoices(session)

        with tenant_scope(bind_tenant(TenantId("acme"))), Session(session.bind) as fresh:
            # SELECT count(*) FROM _Invoice -- column_descriptions includes
            # a literal/function entry with entity=None.
            stmt = select(func.count(_Invoice.id))
            result = fresh.execute(stmt).scalar()
            # Count reflects acme-filtered rows (2 acme), since the
            # _Invoice entity is still in column_descriptions and
            # gets the with_loader_criteria treatment via include_aliases.
            assert result == 2
