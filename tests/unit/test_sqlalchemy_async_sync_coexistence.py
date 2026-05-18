"""Integration tests verifying async + sync TenantShield helpers coexist en same process.

Per Tarea 4A.0 Scenario 7: ``ContextVar`` propagates across
``asyncio.to_thread`` boundary because asyncio's per-task
``copy_context()`` semantics include the worker thread's context copy.
Tarea 4A.0 Scenarios 1 + 2 reconfirm intra-task propagation +
cross-task isolation.

This module formalizes those findings into integration tests
verifying mixed sync / async architectures common in real adopter
deployments:

- Async route or task sets tenant via ``AsyncSessionScope``; sync
  background utility called via ``asyncio.to_thread`` reads same
  scope.
- Phase 3A enforcement applies regardless of which flavor (sync or
  async) executes the DB operation -- the same Phase 3A handler
  dispatch fires for both ``Session`` and ``AsyncSession``.
- Concurrent ``asyncio.gather`` tasks each calling ``to_thread`` keep
  per-task tenant isolation (no cross-task leak).
- Cross-tenant writes still blocked when the async outer scope and
  the sync inner DB operation reference different tenants implicitly.

Engine separation: sync and async tests use separate ``Session`` and
``AsyncSession`` engines respectively. SQLite ``:memory:`` is
per-connection; sync (``sqlite``) and async (``sqlite+aiosqlite``)
drivers cannot share a connection. This is an empirical constraint
of the SQLite drivers, not a TenantShield limitation; real adopters
using PostgreSQL/MySQL via ``asyncpg``/``aiomysql`` would share a
database across flavors. The coexistence under test is the TenantShield
ContextVar binding mechanism, not cross-flavor DB connection sharing.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from tenantshield import try_current_tenant
from tenantshield.adapters.sqlalchemy import (
    AsyncSessionScope,
    SessionScope,
    tenant_aware,
)
from tenantshield.exceptions import CrossTenantAccessError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from sqlalchemy.ext.asyncio import AsyncSession


class _Base(DeclarativeBase):
    """Test-local declarative base."""


@tenant_aware
class _Invoice(_Base):
    __tablename__ = "test_invoice_coexistence"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()


@pytest.fixture
def sync_factory() -> Generator[sessionmaker[Session], None, None]:
    """Sync sessionmaker over in-memory SQLite (per-test isolated).

    Uses ``StaticPool`` + ``check_same_thread=False`` per Rule 56:
    coexistence tests dispatch sync operations via
    ``asyncio.to_thread``, which runs them on a worker thread.
    SQLite ``:memory:`` is per-connection; ``StaticPool`` shares a
    single connection across threads so the schema created on the
    main thread is visible to operations dispatched on worker threads.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest_asyncio.fixture
async def aio_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Async sessionmaker over in-memory aiosqlite (per-test isolated)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


class TestAsyncToSyncContextVarPropagation:
    """ContextVar set in async context visible in sync code via asyncio.to_thread."""

    @pytest.mark.asyncio
    async def test_async_scope_visible_in_sync_via_to_thread(self) -> None:
        """AsyncSessionScope sets tenant; sync function via to_thread observes scope."""

        def sync_observer() -> str | None:
            ctx = try_current_tenant()
            return str(ctx.tenant_id) if ctx else None

        async with AsyncSessionScope(tenant="acme"):
            observed = await asyncio.to_thread(sync_observer)
            assert observed == "acme"

    @pytest.mark.asyncio
    async def test_sync_db_write_under_async_scope_enforces_auto_inject(
        self,
        sync_factory: sessionmaker[Session],
    ) -> None:
        """Sync Session insert inside to_thread under AsyncSessionScope auto-injects tenant."""

        def sync_insert() -> str:
            with sync_factory() as session:
                invoice = _Invoice()
                session.add(invoice)
                session.flush()
                inserted_tenant = invoice.tenant_id
                session.commit()
                return inserted_tenant

        async with AsyncSessionScope(tenant="acme"):
            tenant_id = await asyncio.to_thread(sync_insert)
            assert tenant_id == "acme"


class TestConcurrentAsyncIsolationWithToThread:
    """asyncio.gather isolation preserved despite shared sync utilities."""

    @pytest.mark.asyncio
    async def test_gather_tasks_with_to_thread_calls_isolated(self) -> None:
        """Concurrent async tasks each calling to_thread maintain per-task tenant binding."""

        def sync_observer() -> str | None:
            ctx = try_current_tenant()
            return str(ctx.tenant_id) if ctx else None

        async def request_handler(tenant_name: str) -> str | None:
            async with AsyncSessionScope(tenant=tenant_name):
                return await asyncio.to_thread(sync_observer)

        results = await asyncio.gather(
            request_handler("acme"),
            request_handler("globex"),
            request_handler("initech"),
        )
        assert results == ["acme", "globex", "initech"]


class TestCrossBoundaryEnforcement:
    """Phase 3A enforcement applies regardless of sync/async boundary direction."""

    @pytest.mark.asyncio
    async def test_cross_tenant_sync_write_under_async_scope_raises(
        self,
        sync_factory: sessionmaker[Session],
    ) -> None:
        """Async-set scope acme; sync insert with explicit tenant=globex raises."""

        def sync_cross_tenant_insert() -> None:
            with sync_factory() as session:
                invoice = _Invoice(tenant_id="globex")
                session.add(invoice)
                session.flush()

        async with AsyncSessionScope(tenant="acme"):
            with pytest.raises(CrossTenantAccessError):
                await asyncio.to_thread(sync_cross_tenant_insert)

    @pytest.mark.asyncio
    async def test_async_write_under_async_scope_after_sync_seed(
        self,
        sync_factory: sessionmaker[Session],
        aio_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Sync engine seeded under one scope; async engine works under separate scope."""

        def sync_seed() -> None:
            with SessionScope(tenant="acme"), sync_factory() as session:
                session.add(_Invoice())
                session.commit()

        await asyncio.to_thread(sync_seed)

        async with AsyncSessionScope(tenant="globex"), aio_factory() as fresh:
            fresh.add(_Invoice())
            await fresh.flush()
            result = await fresh.execute(select(_Invoice))
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].tenant_id == "globex"
            await fresh.commit()
