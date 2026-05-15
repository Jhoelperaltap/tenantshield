"""Edge case tests for SQLAlchemy adapter bulk operations.

Documents bulk operations bypass mapper-scoped events by design.
This is an architectural constraint inherited from SQLAlchemy's event
system, not a TenantShield bug. Adopters using bulk operations
(Core ``insert()``, ``update()``, ``delete()`` statements with
multi-row values) must ensure tenant coherence manually.

Pattern analogous to Django adapter's ``_base_manager`` semantics:
bypass mechanisms exist by design; library cannot prevent them
without breaking framework idioms.

Materializes DR-024 (bulk operations bypass).

Verification uses raw SQL (``text()``) where appropriate to bypass
``do_orm_execute`` read filtering and observe actual database state.

See also
--------

- ADR-0007 (event-based enforcement consequences).
- SA documentation:
  <https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html>.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, delete, insert, select, text, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tenantshield import TenantId, bind_tenant, tenant_scope
from tenantshield.adapters.sqlalchemy import tenant_aware

if TYPE_CHECKING:
    from collections.abc import Generator


class _Base(DeclarativeBase):
    """Test-local declarative base."""


@tenant_aware
class _Invoice(_Base):
    __tablename__ = "test_invoice_bulk_ops"
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


class TestBulkOperationsBypass:
    """Verify bulk operations bypass mapper events by design.

    These tests document the architectural constraint that bulk
    operations skip mapper-scoped events (``before_insert``,
    ``before_update``, ``before_delete``). Adopters must enforce
    tenant coherence manually when using bulk patterns.

    DR-024 documents this constraint.
    """

    def test_bulk_insert_bypasses_before_insert_enforcement(self, session: Session) -> None:
        """Bulk insert via Core ``insert()`` does NOT fire ``before_insert``.

        Cross-tenant rows can be inserted via bulk pattern even within
        tenant scope. Adopters using bulk insert must validate
        tenant_id manually.

        Verification via raw SQL bypasses ``do_orm_execute`` read
        filtering to observe true DB state.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.execute(
                insert(_Invoice).values(
                    [
                        {"tenant_id": "acme", "amount": 100},
                        {"tenant_id": "globex", "amount": 200},
                    ]
                )
            )
            session.commit()

        rows = session.execute(
            text("SELECT tenant_id, amount FROM test_invoice_bulk_ops ORDER BY id")
        ).all()
        assert len(rows) == 2
        tenant_ids = {r[0] for r in rows}
        assert tenant_ids == {"acme", "globex"}

    def test_bulk_insert_without_scope_does_not_raise(self, session: Session) -> None:
        """Bulk insert without scope does NOT raise MissingTenantContextError.

        Mapper events are bypassed, so the ``MissingTenantContextError``
        check in ``before_insert`` does not fire. Adopters must
        explicitly check active scope before bulk operations.
        """
        session.execute(insert(_Invoice).values({"tenant_id": "acme", "amount": 999}))
        session.commit()

        rows = session.execute(text("SELECT count(*) FROM test_invoice_bulk_ops")).scalar()
        assert rows == 1

    def test_bulk_update_bypasses_before_update_enforcement(self, session: Session) -> None:
        """Bulk update via Core ``update()`` does NOT fire ``before_update``.

        Cross-tenant updates via bulk pattern are NOT prevented.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(tenant_id="acme", amount=100))
            session.commit()
        with tenant_scope(bind_tenant(TenantId("globex"))):
            session.add(_Invoice(tenant_id="globex", amount=200))
            session.commit()

        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.execute(
                update(_Invoice).where(_Invoice.tenant_id == "globex").values(amount=999)
            )
            session.commit()

        # Verify via raw SQL: globex amount was updated despite acme scope.
        globex_amount = session.execute(
            text("SELECT amount FROM test_invoice_bulk_ops WHERE tenant_id='globex'")
        ).scalar()
        assert globex_amount == 999

    def test_bulk_delete_bypasses_before_delete_enforcement(self, session: Session) -> None:
        """Bulk delete via Core ``delete()`` does NOT fire ``before_delete``.

        Cross-tenant deletes via bulk pattern are NOT prevented.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(tenant_id="acme", amount=100))
            session.commit()
        with tenant_scope(bind_tenant(TenantId("globex"))):
            session.add(_Invoice(tenant_id="globex", amount=200))
            session.commit()

        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.execute(delete(_Invoice).where(_Invoice.tenant_id == "globex"))
            session.commit()

        # Verify via raw SQL: globex row deleted despite acme scope.
        globex_count = session.execute(
            text("SELECT count(*) FROM test_invoice_bulk_ops WHERE tenant_id='globex'")
        ).scalar()
        assert globex_count == 0


class TestBulkSelectFiltering:
    """Verify SELECT operations are filtered by do_orm_execute.

    Read filtering operates at session-scoped event level, which fires
    for ORM SELECT statements. SELECT IS filtered even though bulk
    writes bypass mapper events.
    """

    def test_bulk_select_filtered_by_scope(self, session: Session) -> None:
        """SELECT statements ARE filtered by tenant via do_orm_execute.

        Even though writes bypass mapper events in bulk, reads via
        ``select()`` ARE filtered via ``do_orm_execute`` event +
        ``with_loader_criteria`` injection.
        """
        with tenant_scope(bind_tenant(TenantId("acme"))):
            session.add(_Invoice(tenant_id="acme", amount=100))
            session.add(_Invoice(tenant_id="acme", amount=150))
            session.commit()
        with tenant_scope(bind_tenant(TenantId("globex"))):
            session.add(_Invoice(tenant_id="globex", amount=999))
            session.commit()

        with tenant_scope(bind_tenant(TenantId("acme"))):
            rows = session.execute(select(_Invoice)).scalars().all()
            assert len(rows) == 2
            assert all(r.tenant_id == "acme" for r in rows)
