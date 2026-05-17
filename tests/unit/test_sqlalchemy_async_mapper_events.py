"""Integration tests verifying mapper events fire transparently under AsyncSession.

Per Tarea 4A.0 Scenario 4: mapper events dispatched at sync engine flush
layer; ``AsyncSession.flush()`` delegates via greenlet; events fire
identically to sync ``Session.flush()``. SQLAlchemy routes
``AsyncSession`` operations through ``AsyncSession.sync_session_class``
(= ``Session``), so the registration ``event.listen(cls,
"before_insert", ...)`` from Phase 3A ``events.py`` dispatches for both
sync and async flush paths.

This module verifies TenantShield's Phase 3A write enforcement
(``register_write_enforcement(cls)``) reuses transparently for
``AsyncSession`` contexts. No new event handlers are introduced; Phase
3A handler dispatch is verified empirically end-to-end:

- ``MissingTenantContextError`` raised when no scope is active during
  flush.
- Tenant auto-injection on insert.
- ``CrossTenantAccessError`` raised on cross-tenant insert/update/delete.

Composition with ``AsyncSessionScope`` and
``bind_async_session_to_tenant`` is exercised explicitly to confirm
the new Sub-fase 4A helpers integrate with the Phase 3A enforcement
layer end-to-end.

Pattern paralelo to ``test_sqlalchemy_events.py`` (Phase 3A precedent
for sync ``Session``) adapted to ``AsyncSession`` + aiosqlite. The
fixture exposes an ``async_sessionmaker`` factory so tests needing
multiple sessions (seed outside scope, modify inside another) can
spawn fresh sessions sharing the same engine -- paralelo to Phase 3A's
``Session(session.bind)`` pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tenantshield import TenantId, atenant_scope, bind_tenant
from tenantshield.adapters.sqlalchemy import (
    AsyncSessionScope,
    bind_async_session_to_tenant,
    tenant_aware,
)
from tenantshield.exceptions import CrossTenantAccessError, MissingTenantContextError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


class _Base(DeclarativeBase):
    """Test-local declarative base."""


@tenant_aware
class _Invoice(_Base):
    __tablename__ = "test_invoice_async_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()


@pytest_asyncio.fixture
async def aio_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Provide an aiosqlite ``async_sessionmaker`` factory for each test.

    Tests needing multiple sessions (seed outside scope; modify in fresh
    session) spawn them via ``async with aio_factory() as session:``.
    Pattern paralelo to Phase 3A ``Session(session.bind)`` reuse of a
    shared engine across multiple sync sessions.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _insert_seed_invoice_async(factory: async_sessionmaker[AsyncSession], tenant: str) -> int:
    """Insert a seed invoice within tenant scope; return its id.

    Paralelo to Phase 3A ``_insert_seed_invoice`` helper. Async helper
    for UPDATE / DELETE tests that need pre-existing rows seeded under
    one tenant before being modified under another tenant scope.
    """
    async with atenant_scope(bind_tenant(TenantId(tenant))), factory() as s:
        inv = _Invoice(tenant_id=tenant)
        s.add(inv)
        await s.flush()
        inv_id = inv.id
        await s.commit()
    return inv_id


class TestAsyncBeforeInsertEnforcement:
    """Verify before_insert enforcement under AsyncSession.flush."""

    @pytest.mark.asyncio
    async def test_insert_without_scope_raises_missing_context(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with aio_factory() as session:
            invoice = _Invoice()
            session.add(invoice)
            with pytest.raises(MissingTenantContextError) as exc_info:
                await session.flush()

            assert "before_insert" in exc_info.value.operation
            assert "_Invoice" in exc_info.value.operation

    @pytest.mark.asyncio
    async def test_insert_with_scope_auto_injects_tenant_id(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with atenant_scope(bind_tenant(TenantId("acme"))), aio_factory() as session:
            invoice = _Invoice()
            session.add(invoice)
            await session.flush()
            assert invoice.tenant_id == "acme"
            await session.commit()

    @pytest.mark.asyncio
    async def test_insert_with_mismatched_tenant_raises_cross_tenant(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with atenant_scope(bind_tenant(TenantId("acme"))), aio_factory() as session:
            invoice = _Invoice(tenant_id="globex")
            session.add(invoice)
            with pytest.raises(CrossTenantAccessError) as exc_info:
                await session.flush()

            assert str(exc_info.value.tenant_id_expected) == "acme"
            assert str(exc_info.value.tenant_id_actual) == "globex"
            assert "_Invoice" in exc_info.value.model


class TestAsyncBeforeUpdateEnforcement:
    """Verify before_update enforcement under AsyncSession.flush."""

    @pytest.mark.asyncio
    async def test_cross_tenant_update_raises_cross_tenant(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        inv_id = await _insert_seed_invoice_async(aio_factory, "globex")

        # Load OUTSIDE scope so do_orm_execute does not filter the
        # globex row out. Modify INSIDE acme scope to trigger
        # before_update under a mismatching context.
        async with aio_factory() as fresh:
            inv = await fresh.get(_Invoice, inv_id)
            assert inv is not None
            async with atenant_scope(bind_tenant(TenantId("acme"))):
                inv.tenant_id = "globex"
                with pytest.raises(CrossTenantAccessError) as exc_info:
                    await fresh.flush()

                assert str(exc_info.value.tenant_id_expected) == "acme"
                assert str(exc_info.value.tenant_id_actual) == "globex"


class TestAsyncBeforeDeleteEnforcement:
    """Verify before_delete enforcement under AsyncSession.flush."""

    @pytest.mark.asyncio
    async def test_cross_tenant_delete_raises_cross_tenant(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        inv_id = await _insert_seed_invoice_async(aio_factory, "globex")

        # Load OUTSIDE scope to bypass read filter; delete INSIDE acme
        # scope to trigger before_delete under mismatching context.
        async with aio_factory() as fresh:
            inv = await fresh.get(_Invoice, inv_id)
            assert inv is not None
            async with atenant_scope(bind_tenant(TenantId("acme"))):
                await fresh.delete(inv)
                with pytest.raises(CrossTenantAccessError) as exc_info:
                    await fresh.flush()

                assert str(exc_info.value.tenant_id_expected) == "acme"
                assert str(exc_info.value.tenant_id_actual) == "globex"


class TestAsyncEnforcementWithAsyncSessionScope:
    """Verify Phase 3A enforcement integrates con AsyncSessionScope helper."""

    @pytest.mark.asyncio
    async def test_async_session_scope_auto_injects_tenant(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with AsyncSessionScope(tenant="acme"), aio_factory() as session:
            invoice = _Invoice()
            session.add(invoice)
            await session.flush()
            assert invoice.tenant_id == "acme"
            await session.commit()

    @pytest.mark.asyncio
    async def test_bind_async_session_to_tenant_enforces_cross_tenant(
        self, aio_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with bind_async_session_to_tenant("acme"), aio_factory() as session:
            invoice = _Invoice(tenant_id="globex")
            session.add(invoice)
            with pytest.raises(CrossTenantAccessError):
                await session.flush()
