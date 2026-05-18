"""FastAPI + TenantShield SQLAlchemy adapter example (AsyncSession-native).

Phase 4 Decision 7-A: this example replaces the Phase 3 sync FastAPI
example (which used ``run_in_threadpool`` wrapping sync ``Session`` from
``async def`` handlers). The async-native pattern eliminates the
threadpool indirection: handlers consume ``AsyncSession`` directly via
FastAPI ``Depends``, and TenantShield enforcement applies transparently
through Phase 3A event handler reuse (mapper events + ``do_orm_execute``
fire identically for sync and async ``Session`` paths because
``AsyncSession.sync_session_class = Session``; empirically validated in
Tarea 4A.0 Scenarios 3 and 4).

Demonstrates:

- ASGI middleware integration with ``TenantSessionMiddleware``.
- Dual-mode resolver capability (Sub-fase 4A, Decision 3-A): the
  default ``app`` uses a synchronous callable resolver (Phase 3B
  precedent), while ``strict_app`` showcases an asynchronous resolver
  pattern (Sub-fase 4A extension).
- ``AsyncSession`` consumed directly via ``Depends`` -- no threadpool
  wrap, no event-loop blocking.
- Strict mode opt-in (``on_missing_tenant='raise'``) via separate
  ``strict_app`` instance.

Run::

    uvicorn app:app --reload

Test::

    pytest tests/

Migration from Phase 3 sync pattern: adopters previously using sync
``Session`` + ``run_in_threadpool`` should switch to ``AsyncSession``
+ ``Depends`` per this example. Existing TenantShield Phase 3A
decorations (``@tenant_aware``) require no changes -- the same event
handlers serve both flavors.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from tenantshield import TenantId, atenant_scope, bind_tenant
from tenantshield.adapters.sqlalchemy import TenantSessionMiddleware

from models import Base, Invoice

# Async engine + StaticPool for in-memory SQLite shared across requests.
# Rule 56 applies: in-memory SQLite + threaded test client requires
# StaticPool + check_same_thread=False. Real adopters with file-backed
# SQLite or PostgreSQL/MySQL/aiosqlite-file omit pool configuration.
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def _init_and_seed() -> None:
    """Initialize schema + seed demo invoices for acme and globex tenants.

    Executed once at module import via ``asyncio.run``. The schema and
    seed rows persist for the lifetime of the module-level engine
    (StaticPool keeps a single connection alive). Idempotent seeding per
    Rule 58: re-running ``_init_and_seed`` against the same engine
    is safe because schema creation uses ``create_all`` (idempotent)
    and tests do not re-seed via this helper.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with (
        atenant_scope(bind_tenant(TenantId("acme"))),
        async_session_factory() as session,
    ):
        session.add(Invoice(amount=100, description="Acme invoice 1"))
        session.add(Invoice(amount=200, description="Acme invoice 2"))
        await session.commit()

    async with (
        atenant_scope(bind_tenant(TenantId("globex"))),
        async_session_factory() as session,
    ):
        session.add(Invoice(amount=999, description="Globex invoice 1"))
        await session.commit()


asyncio.run(_init_and_seed())


async def get_async_session() -> Any:
    """FastAPI dependency yielding an ``AsyncSession`` per request.

    Adopters typically configure this via a shared module providing
    the engine + session factory; the dependency yields one session
    per route invocation and closes on completion.
    """
    async with async_session_factory() as session:
        yield session


def resolve_tenant_from_scope(scope: dict[str, Any]) -> str | None:
    """Synchronous resolver extracting ``X-Tenant-ID`` from ASGI scope.

    Canonical callable resolver pattern per Sub-fase 3B BLOCKER #30
    resolution: Phase 2B Django strategy classes are not reusable
    here. Adopters write small framework-specific resolvers like this
    one. Compatible with ``TenantSessionMiddleware`` synchronously
    (Phase 3B precedent).
    """
    for name, value in scope.get("headers", []):
        if name == b"x-tenant-id":
            return value.decode("latin-1")
    return None


async def resolve_tenant_from_scope_async(scope: dict[str, Any]) -> str | None:
    """Asynchronous resolver alternative (Sub-fase 4A dual-mode capability).

    Pattern for adopters resolving tenant from an async source -- for
    example, decoding a JWT against an async session-store, querying
    an async database for a session-token-to-tenant mapping, or
    calling an external async authentication service.

    ``TenantSessionMiddleware`` detects the coroutine return via
    ``inspect.iscoroutine`` and awaits transparently. Sync and async
    resolvers are interchangeable from the middleware's perspective.
    """
    # Realistic async resolvers do real async work here (DB / API call).
    # The header lookup is synchronous; this signature still applies as
    # a documentation pattern for async resolver shape.
    for name, value in scope.get("headers", []):
        if name == b"x-tenant-id":
            return value.decode("latin-1")
    return None


# Default app: synchronous resolver + fall-through mode (DR-022).
app = FastAPI(title="TenantShield SQLAlchemy + FastAPI example (async)")
app.add_middleware(
    TenantSessionMiddleware,
    resolve_tenant=resolve_tenant_from_scope,
)


# Strict app: asynchronous resolver + strict mode (DR-026).
# Demonstrates Sub-fase 4A dual-mode resolver capability.
strict_app = FastAPI(title="TenantShield strict mode demo (async resolver)")
strict_app.add_middleware(
    TenantSessionMiddleware,
    resolve_tenant=resolve_tenant_from_scope_async,
    on_missing_tenant="raise",
)


@app.get("/invoices")
async def get_invoices(
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """Async route returning tenant-filtered invoices.

    Phase 3A ``do_orm_execute`` event filters the ``SELECT`` by active
    tenant scope automatically. No manual ``WHERE tenant_id = ...``
    clauses needed.

    Compared to the Phase 3 sync example: no ``run_in_threadpool``
    wrap, no sync ``Session()`` calls inside ``async def``. Direct
    ``AsyncSession`` consumption is the canonical async-native
    pattern.
    """
    result = await session.execute(select(Invoice))
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "amount": r.amount,
            "description": r.description,
        }
        for r in rows
    ]


@strict_app.get("/invoices")
async def get_invoices_strict(
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """Strict mode endpoint: middleware raises if no ``X-Tenant-ID`` header.

    The strict app's resolver is the asynchronous variant
    (``resolve_tenant_from_scope_async``); the middleware awaits the
    coroutine and applies the same strict-mode rule when the result
    is ``None``.
    """
    result = await session.execute(select(Invoice))
    rows = result.scalars().all()
    return [{"id": r.id, "tenant_id": r.tenant_id} for r in rows]
