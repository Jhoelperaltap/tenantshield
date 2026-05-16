"""Edge case tests for SQLAlchemy adapter raw SQL behavior.

Documents raw SQL via ``text()`` bypasses ALL tenant enforcement:
- ``do_orm_execute`` skips raw statements (``is_orm_statement=False``).
- Mapper-scoped events (``before_insert``, ``before_update``,
  ``before_delete``) fire only on ORM-mapped operations, NOT on
  ``text()`` SQL.

This is an intentional architectural constraint matching Django
adapter's ``_base_manager`` semantics: raw SQL is the documented
escape hatch for cases requiring bypass.

Materializes DR-023 (raw SQL bypass semantics).

See also
--------

- ADR-0007 (event-based enforcement consequences).
- DR-024 (bulk operations bypass, Tarea 3A.6 precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tenantshield import TenantId, bind_tenant, tenant_scope
from tenantshield.adapters.sqlalchemy import tenant_aware

if TYPE_CHECKING:
    from collections.abc import Generator


class _Base(DeclarativeBase):
    """Test-local declarative base."""


@tenant_aware
class _Invoice(_Base):
    __tablename__ = "test_invoice_raw_sql"
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


def _seed_cross_tenant(session: Session) -> None:
    """Helper: seed 2 acme + 1 globex invoices via ORM (proper events)."""
    with tenant_scope(bind_tenant(TenantId("acme"))):
        session.add(_Invoice(tenant_id="acme", amount=100))
        session.add(_Invoice(tenant_id="acme", amount=200))
        session.commit()
    with tenant_scope(bind_tenant(TenantId("globex"))):
        session.add(_Invoice(tenant_id="globex", amount=999))
        session.commit()


class TestRawSqlSelectBypass:
    """Verify raw SQL SELECT bypasses do_orm_execute filter."""

    def test_raw_select_within_scope_returns_all_rows(self, session: Session) -> None:
        """Raw SELECT via text() returns ALL rows, ignoring active scope.

        Adopters using raw SQL for SELECT must filter by tenant_id
        manually in their query string.
        """
        _seed_cross_tenant(session)

        with tenant_scope(bind_tenant(TenantId("acme"))):
            result = session.execute(
                text("SELECT id, tenant_id, amount FROM test_invoice_raw_sql ORDER BY id")
            )
            rows = result.fetchall()

        assert len(rows) == 3
        tenant_ids = {row[1] for row in rows}
        assert tenant_ids == {"acme", "globex"}

    def test_orm_select_filters_but_raw_select_does_not(self, session: Session) -> None:
        """Same scope, different statement type: ORM filters, raw does not."""
        _seed_cross_tenant(session)

        with tenant_scope(bind_tenant(TenantId("acme"))):
            orm_rows = session.execute(select(_Invoice)).scalars().all()
            raw_rows = session.execute(text("SELECT id FROM test_invoice_raw_sql")).fetchall()

        assert len(orm_rows) == 2
        assert len(raw_rows) == 3


class TestRawSqlWriteBypass:
    """Verify raw SQL writes bypass mapper-scoped enforcement events."""

    def test_raw_insert_cross_tenant_does_not_raise(self, session: Session) -> None:
        """Raw INSERT bypasses before_insert; cross-tenant inserts succeed."""
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.execute(
                text("INSERT INTO test_invoice_raw_sql (tenant_id, amount) VALUES ('globex', 666)")
            )
            session.commit()

        count = session.execute(
            text("SELECT COUNT(*) FROM test_invoice_raw_sql WHERE tenant_id = :t"),
            {"t": "globex"},
        ).scalar_one()
        assert count == 1

    def test_raw_insert_without_scope_does_not_raise(self, session: Session) -> None:
        """Raw INSERT without scope succeeds (no MissingTenantContextError)."""
        session.execute(
            text("INSERT INTO test_invoice_raw_sql (tenant_id, amount) VALUES ('acme', 999)")
        )
        session.commit()

        count = session.execute(text("SELECT COUNT(*) FROM test_invoice_raw_sql")).scalar_one()
        assert count == 1

    def test_raw_update_cross_tenant_does_not_raise(self, session: Session) -> None:
        """Raw UPDATE bypasses before_update; cross-tenant updates succeed."""
        _seed_cross_tenant(session)

        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.execute(
                text("UPDATE test_invoice_raw_sql SET amount = 1234 WHERE tenant_id = 'globex'")
            )
            session.commit()

        amounts = [
            row[0]
            for row in session.execute(
                text("SELECT amount FROM test_invoice_raw_sql WHERE tenant_id = 'globex'")
            ).fetchall()
        ]
        assert amounts == [1234]

    def test_raw_delete_cross_tenant_does_not_raise(self, session: Session) -> None:
        """Raw DELETE bypasses before_delete; cross-tenant deletes succeed."""
        _seed_cross_tenant(session)

        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.execute(text("DELETE FROM test_invoice_raw_sql WHERE tenant_id = 'globex'"))
            session.commit()

        count = session.execute(
            text("SELECT COUNT(*) FROM test_invoice_raw_sql WHERE tenant_id = 'globex'")
        ).scalar_one()
        assert count == 0


class TestRawSqlEventSemantics:
    """Verify do_orm_execute correctly skips raw text statements.

    Empirically: do_orm_execute DOES fire for raw text() statements,
    but with ``is_orm_statement=False``. The handler's guard clause
    (``if not (is_select and is_orm_statement): return``) skips early.
    """

    def test_raw_select_executes_without_errors(self, session: Session) -> None:
        """Raw SELECT executes cleanly; do_orm_execute handler does not crash."""
        result = session.execute(text("SELECT 1 AS one"))
        assert result.scalar_one() == 1

    def test_raw_select_with_active_scope_executes_cleanly(self, session: Session) -> None:
        """Raw SELECT under active scope; handler skips gracefully."""
        with tenant_scope(bind_tenant(TenantId("acme"))):
            result = session.execute(text("SELECT 42 AS answer"))
            assert result.scalar_one() == 42
