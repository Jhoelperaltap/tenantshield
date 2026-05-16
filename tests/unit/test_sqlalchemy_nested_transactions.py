"""Edge case tests for SQLAlchemy adapter nested transactions + savepoints.

Verifies tenant enforcement holds correctly across:

- Explicit ``Session.begin_nested()`` (SAVEPOINT).
- Savepoint rollback (inner failures don't affect outer transactions).
- Scope changes within savepoints.
- Reads inside savepoints (do_orm_execute still filters).
- UPDATE/DELETE inside savepoints (cross-tenant raises).

Enforcement is event-driven and fires at flush time, independent of
transaction nesting structure. SAVEPOINTs provide DB-level isolation
of changes; tenant enforcement holds at every level.

Distinct from DR-023 (raw SQL bypass) and DR-024 (bulk ops bypass):
nested transactions do NOT bypass enforcement when using standard
ORM operations.

See also
--------

- ADR-0007 (event-based enforcement consequences).
- SA documentation:
  <https://docs.sqlalchemy.org/en/20/orm/session_transaction.html>.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tenantshield import TenantId, bind_tenant, tenant_scope
from tenantshield.adapters.sqlalchemy import tenant_aware
from tenantshield.exceptions import CrossTenantAccessError

if TYPE_CHECKING:
    from collections.abc import Generator


class _SimulatedRollbackError(Exception):
    """Test-local exception used to trigger savepoint rollback."""


class _Base(DeclarativeBase):
    """Test-local declarative base."""


@tenant_aware
class _Invoice(_Base):
    __tablename__ = "test_invoice_nested_tx"
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


class TestNestedTransactionInsertEnforcement:
    """Verify before_insert event fires correctly inside savepoints."""

    def test_insert_inside_savepoint_within_scope_succeeds(self, session: Session) -> None:
        """INSERT inside savepoint within tenant scope persists correctly."""
        with tenant_scope(bind_tenant(TenantId("acme"))), session.begin_nested():
            inv = _Invoice(amount=100)
            session.add(inv)
            session.flush()
            assert inv.tenant_id == "acme"
        session.commit()

        count = session.execute(text("SELECT COUNT(*) FROM test_invoice_nested_tx")).scalar_one()
        assert count == 1

    def test_savepoint_rollback_undoes_insert(self, session: Session) -> None:
        """Savepoint rollback removes inner INSERT; outer INSERT persists."""
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(amount=100))
            session.flush()

            with (  # noqa: PT012
                pytest.raises(_SimulatedRollbackError),
                session.begin_nested(),
            ):
                session.add(_Invoice(amount=200))
                session.flush()
                raise _SimulatedRollbackError

            session.commit()

        rows = session.execute(
            text("SELECT amount FROM test_invoice_nested_tx ORDER BY id")
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 100

    def test_cross_tenant_insert_inside_savepoint_raises(self, session: Session) -> None:
        """Cross-tenant INSERT inside savepoint raises CrossTenantAccessError.

        Enforcement holds at nested transaction boundaries.
        Security-critical verification.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            with (  # noqa: PT012
                pytest.raises(CrossTenantAccessError) as exc_info,
                session.begin_nested(),
            ):
                session.add(_Invoice(tenant_id="globex", amount=999))
                session.flush()

            assert str(exc_info.value.tenant_id_expected) == "acme"
            assert str(exc_info.value.tenant_id_actual) == "globex"

            session.rollback()

    def test_scope_change_inside_savepoint_honored(self, session: Session) -> None:
        """Scope change within savepoint affects subsequent INSERTs.

        Tenant context is event-driven; new scope inside savepoint
        binds new tenant for subsequent operations.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(amount=100))
            session.flush()

            with (
                tenant_scope(bind_tenant(TenantId("globex"))),
                session.begin_nested(),
            ):
                session.add(_Invoice(amount=200))
                session.flush()

            session.commit()

        rows = session.execute(
            text("SELECT tenant_id, amount FROM test_invoice_nested_tx ORDER BY id")
        ).fetchall()
        assert len(rows) == 2
        assert rows[0] == ("acme", 100)
        assert rows[1] == ("globex", 200)


class TestNestedTransactionReadFiltering:
    """Verify do_orm_execute read filter holds inside savepoints."""

    def test_read_inside_savepoint_filters_by_scope(self, session: Session) -> None:
        """Reads inside savepoint apply tenant filter via do_orm_execute.

        Session-scoped event independent of transaction nesting.
        """
        session.execute(
            text(
                "INSERT INTO test_invoice_nested_tx (tenant_id, amount) "
                "VALUES ('acme', 100), ('globex', 200)"
            )
        )
        session.commit()

        with tenant_scope(bind_tenant(TenantId("acme"))), session.begin_nested():
            rows = session.execute(select(_Invoice)).scalars().all()
            assert len(rows) == 1
            assert rows[0].tenant_id == "acme"

    def test_read_filter_consistent_across_savepoint_boundary(self, session: Session) -> None:
        """Read filter applies before, inside, and after savepoint identically."""
        session.execute(
            text(
                "INSERT INTO test_invoice_nested_tx (tenant_id, amount) "
                "VALUES ('acme', 100), ('acme', 200), ('globex', 999)"
            )
        )
        session.commit()

        with tenant_scope(bind_tenant(TenantId("acme"))):
            before = session.execute(select(_Invoice)).scalars().all()
            assert len(before) == 2

            with session.begin_nested():
                inside = session.execute(select(_Invoice)).scalars().all()
                assert len(inside) == 2

            after = session.execute(select(_Invoice)).scalars().all()
            assert len(after) == 2


class TestNestedTransactionUpdateDeleteEnforcement:
    """Verify UPDATE/DELETE enforcement inside savepoints."""

    def test_update_inside_savepoint_in_matching_scope_succeeds(self, session: Session) -> None:
        """UPDATE inside savepoint within matching scope succeeds."""
        with tenant_scope(bind_tenant(TenantId("acme"))):
            inv = _Invoice(amount=100)
            session.add(inv)
            session.flush()
            inv_id = inv.id
            session.commit()

        with tenant_scope(bind_tenant(TenantId("acme"))), session.begin_nested():
            inv = session.get(_Invoice, inv_id)
            assert inv is not None
            inv.amount = 999
            session.flush()
        session.commit()

        amount = session.execute(
            text("SELECT amount FROM test_invoice_nested_tx WHERE id = :i"),
            {"i": inv_id},
        ).scalar_one()
        assert amount == 999

    def test_update_inside_savepoint_cross_tenant_raises(self, session: Session) -> None:
        """Cross-tenant UPDATE inside savepoint raises CrossTenantAccessError.

        Pattern: load row OUTSIDE scope (no filter, since do_orm_execute
        falls through on missing scope), then mutate INSIDE acme scope.
        Mirrors precedent from 3A.5 tests.
        """
        with tenant_scope(bind_tenant(TenantId("globex"))):
            inv = _Invoice(amount=200)
            session.add(inv)
            session.flush()
            inv_id = inv.id
            session.commit()

        loaded = session.get(_Invoice, inv_id)
        assert loaded is not None
        assert loaded.tenant_id == "globex"

        with tenant_scope(bind_tenant(TenantId("acme"))):
            loaded.amount = 999
            with pytest.raises(CrossTenantAccessError) as exc_info, session.begin_nested():
                session.flush()

            assert str(exc_info.value.tenant_id_expected) == "acme"
            assert str(exc_info.value.tenant_id_actual) == "globex"

            session.rollback()

    def test_delete_inside_savepoint_cross_tenant_raises(self, session: Session) -> None:
        """Cross-tenant DELETE inside savepoint raises CrossTenantAccessError.

        Same load-outside / mutate-inside pattern as the UPDATE variant.
        """
        with tenant_scope(bind_tenant(TenantId("globex"))):
            inv = _Invoice(amount=200)
            session.add(inv)
            session.flush()
            inv_id = inv.id
            session.commit()

        loaded = session.get(_Invoice, inv_id)
        assert loaded is not None

        with tenant_scope(bind_tenant(TenantId("acme"))):
            with (  # noqa: PT012
                pytest.raises(CrossTenantAccessError) as exc_info,
                session.begin_nested(),
            ):
                session.delete(loaded)
                session.flush()

            assert str(exc_info.value.tenant_id_expected) == "acme"
            assert str(exc_info.value.tenant_id_actual) == "globex"

            session.rollback()
