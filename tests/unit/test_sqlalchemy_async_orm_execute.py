"""Integration tests verifying do_orm_execute fires transparently under AsyncSession.

Per Tarea 4A.0 Scenario 3: ``do_orm_execute`` is dispatched at the SA
session layer; ``AsyncSession.execute()`` routes through
``AsyncSession.sync_session_class`` (= ``Session``), so the registration
``event.listen(Session, "do_orm_execute", ...)`` from Phase 3A
``events.py`` dispatches for both sync and async query paths.

This module verifies TenantShield's Phase 3A read enforcement
(``_do_orm_execute_handler`` injecting ``with_loader_criteria`` based on
active tenant scope) reuses transparently for ``AsyncSession`` contexts.
No new event handlers are introduced; Phase 3A handler dispatch is
verified empirically end-to-end:

- SELECT under a tenant scope returns only that tenant's rows.
- SELECT under no scope returns all rows (fall-through; stricter mode
  is provided by middleware in Sub-fase 3B per DR-022).
- WHERE clauses combine with the tenant filter cleanly.
- Non-tenant-aware models pass through without filter injection.
- Raw SQL via ``text()`` is not an ORM statement and is unaffected.

Composition with ``AsyncSessionScope`` and
``bind_async_session_to_tenant`` is exercised explicitly to confirm
the new Sub-fase 4A helpers integrate with the Phase 3A read
enforcement layer end-to-end.

Pattern paralelo to ``TestDoOrmExecuteEventListener`` in
``test_sqlalchemy_events.py`` (Phase 3A precedent for sync ``Session``)
adapted to ``AsyncSession`` + aiosqlite + multi-session factory fixture
(Pool 4A #9 pattern established in Tarea 4A.3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tenantshield import TenantId, atenant_scope, bind_tenant
from tenantshield.adapters.sqlalchemy import (
    AsyncSessionScope,
    bind_async_session_to_tenant,
    tenant_aware,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


class _Base(DeclarativeBase):
    """Test-local declarative base."""


@tenant_aware
class _Invoice(_Base):
    __tablename__ = "test_invoice_async_orm_execute"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()


class _NonTenantData(_Base):
    """Non-tenant-aware model for edge-case coverage of do_orm_execute."""

    __tablename__ = "test_non_tenant_data_async"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[int] = mapped_column()


@pytest_asyncio.fixture
async def aio_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Provide an aiosqlite ``async_sessionmaker`` factory for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _seed_invoices_async(factory: async_sessionmaker[AsyncSession]) -> None:
    """Seed 2 acme invoices + 1 globex invoice across two scopes."""
    async with atenant_scope(bind_tenant(TenantId("acme"))), factory() as s:
        s.add(_Invoice(tenant_id="acme"))
        s.add(_Invoice(tenant_id="acme"))
        await s.commit()
    async with atenant_scope(bind_tenant(TenantId("globex"))), factory() as s:
        s.add(_Invoice(tenant_id="globex"))
        await s.commit()


class TestAsyncDoOrmExecuteReadFiltering:
    """Verify do_orm_execute filters reads under AsyncSession.execute."""

    @pytest.mark.asyncio
    async def test_select_within_scope_returns_only_scope_rows(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_invoices_async(aio_factory)

        async with atenant_scope(bind_tenant(TenantId("acme"))), aio_factory() as fresh:
            result = await fresh.execute(select(_Invoice))
            rows = result.scalars().all()
            assert len(rows) == 2
            assert all(r.tenant_id == "acme" for r in rows)

    @pytest.mark.asyncio
    async def test_select_within_other_scope_returns_only_other_scope_rows(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_invoices_async(aio_factory)

        async with atenant_scope(bind_tenant(TenantId("globex"))), aio_factory() as fresh:
            result = await fresh.execute(select(_Invoice))
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].tenant_id == "globex"

    @pytest.mark.asyncio
    async def test_select_without_scope_returns_all_rows(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Fall-through behavior: no active scope, no filtering applied.

        Stricter raise-on-missing behavior is provided by middleware in
        Sub-fase 3B per DR-022.
        """
        await _seed_invoices_async(aio_factory)

        async with aio_factory() as fresh:
            result = await fresh.execute(select(_Invoice))
            rows = result.scalars().all()
            assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_filtered_query_with_where_combines_with_tenant_filter(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_invoices_async(aio_factory)

        async with atenant_scope(bind_tenant(TenantId("acme"))), aio_factory() as fresh:
            stmt = select(_Invoice).where(_Invoice.id >= 1)
            result = await fresh.execute(stmt)
            rows = result.scalars().all()
            assert len(rows) == 2
            assert all(r.tenant_id == "acme" for r in rows)


class TestAsyncDoOrmExecuteSpecialCases:
    """Verify do_orm_execute special-case handling under AsyncSession."""

    @pytest.mark.asyncio
    async def test_select_non_tenant_aware_model_passes_through(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Non-tenant-aware model: do_orm_execute skips filter injection."""
        async with aio_factory() as seed:
            seed.add(_NonTenantData(value=42))
            seed.add(_NonTenantData(value=99))
            await seed.commit()

        async with atenant_scope(bind_tenant(TenantId("acme"))), aio_factory() as fresh:
            result = await fresh.execute(select(_NonTenantData))
            rows = result.scalars().all()
            assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_raw_sql_passes_through_without_filter_injection(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Raw SQL (text()) is not an ORM statement; handler short-circuits."""
        async with atenant_scope(bind_tenant(TenantId("acme"))), aio_factory() as session:
            result = await session.execute(text("SELECT 1 AS one"))
            assert list(result) == [(1,)]

    @pytest.mark.asyncio
    async def test_bare_function_in_select_applies_tenant_filter(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """SELECT count(_Invoice.id) reflects tenant-filtered rows."""
        await _seed_invoices_async(aio_factory)

        async with atenant_scope(bind_tenant(TenantId("acme"))), aio_factory() as fresh:
            stmt = select(func.count(_Invoice.id))
            result = await fresh.execute(stmt)
            count = result.scalar()
            assert count == 2


class TestAsyncDoOrmExecuteScopeIntegration:
    """Read filtering integrates con AsyncSessionScope + bind_async_session_to_tenant."""

    @pytest.mark.asyncio
    async def test_read_filtering_under_async_session_scope(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_invoices_async(aio_factory)

        async with AsyncSessionScope(tenant="acme"), aio_factory() as fresh:
            result = await fresh.execute(select(_Invoice))
            rows = result.scalars().all()
            assert len(rows) == 2
            assert all(r.tenant_id == "acme" for r in rows)

    @pytest.mark.asyncio
    async def test_read_filtering_under_bind_async_session_to_tenant(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_invoices_async(aio_factory)

        async with bind_async_session_to_tenant("globex"), aio_factory() as fresh:
            result = await fresh.execute(select(_Invoice))
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].tenant_id == "globex"
