"""FastAPI + TenantShield SQLAlchemy adapter example.

Demonstrates:

- ASGI middleware integration (``TenantSessionMiddleware``).
- Callable resolver pattern for tenant extraction (header-based).
- Sync vs async route handlers with SA ``Session``.
- Strict mode opt-in (``on_missing_tenant='raise'``) via separate
  ``strict_app`` instance.

Run::

    uvicorn app:app --reload

Test::

    pytest tests/

Important: SA Session is sync. Use ``def`` route handlers OR
``async def`` with ``run_in_threadpool``. NEVER call sync Session()
inside ``async def`` without threadpool -- this blocks the event loop.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.concurrency import run_in_threadpool

from tenantshield import TenantId, bind_tenant, tenant_scope
from tenantshield.adapters.sqlalchemy import TenantSessionMiddleware

from models import Base, Invoice


# Database setup with StaticPool for in-memory SQLite shared across threads.
# Real adopters with file-backed SQLite or PostgreSQL/MySQL omit pool config.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)


def _seed_data() -> None:
    """Insert demo data for acme and globex tenants."""
    with tenant_scope(bind_tenant(TenantId("acme"))):
        with SessionLocal() as session:
            session.add(Invoice(amount=100, description="Acme invoice 1"))
            session.add(Invoice(amount=200, description="Acme invoice 2"))
            session.commit()

    with tenant_scope(bind_tenant(TenantId("globex"))):
        with SessionLocal() as session:
            session.add(Invoice(amount=999, description="Globex invoice 1"))
            session.commit()


_seed_data()


def resolve_tenant_from_scope(scope: dict[str, Any]) -> str | None:
    """Extract ``X-Tenant-ID`` header from ASGI scope.

    ASGI scope headers are ``list[tuple[bytes, bytes]]``. Decode to
    ``str`` for TenantShield. Returns ``None`` if header absent.

    Canonical callable resolver pattern per Sub-fase 3B BLOCKER #30
    resolution: Phase 2B strategy classes are Django-bound, NOT
    reusable here. Adopters write small framework-specific resolvers
    like this one.
    """
    for name, value in scope.get("headers", []):
        if name == b"x-tenant-id":
            return value.decode("latin-1")
    return None


# Default app: fall-through on missing tenant (DR-022 backwards-compat).
app = FastAPI(title="TenantShield SQLAlchemy + FastAPI example")
app.add_middleware(
    TenantSessionMiddleware,
    resolve_tenant=resolve_tenant_from_scope,
)


# Strict app: separate instance demonstrating on_missing_tenant='raise'.
strict_app = FastAPI(title="TenantShield strict mode demo")
strict_app.add_middleware(
    TenantSessionMiddleware,
    resolve_tenant=resolve_tenant_from_scope,
    on_missing_tenant="raise",
)


@app.get("/invoices/sync")
def get_invoices_sync() -> list[dict[str, Any]]:
    """Sync handler: SA Session usage is direct and idiomatic.

    Recommended pattern for FastAPI + SQLAlchemy combination.
    Sync handlers are run in a threadpool by FastAPI; SA Session
    operations are blocking but the threadpool prevents event loop
    starvation.
    """
    with SessionLocal() as session:
        rows = session.execute(select(Invoice)).scalars().all()
        return [
            {
                "id": r.id,
                "tenant_id": r.tenant_id,
                "amount": r.amount,
                "description": r.description,
            }
            for r in rows
        ]


@app.get("/invoices/async")
async def get_invoices_async() -> list[dict[str, Any]]:
    """Async handler: SA Session call wrapped in ``run_in_threadpool``.

    Use this pattern when async route handlers must do SA work.
    The ContextVar (tenant scope) propagates correctly across the
    threadpool boundary via Python's ``copy_context()`` semantics
    (Rule 55 / Phase 3B).

    NEVER call sync ``Session()`` directly inside ``async def`` without
    threadpool -- this blocks the event loop.
    """

    def _query() -> list[dict[str, Any]]:
        with SessionLocal() as session:
            rows = session.execute(select(Invoice)).scalars().all()
            return [
                {
                    "id": r.id,
                    "tenant_id": r.tenant_id,
                    "amount": r.amount,
                    "description": r.description,
                }
                for r in rows
            ]

    return await run_in_threadpool(_query)


@strict_app.get("/invoices")
def get_invoices_strict() -> list[dict[str, Any]]:
    """Strict mode endpoint: middleware raises if no ``X-Tenant-ID`` header."""
    with SessionLocal() as session:
        rows = session.execute(select(Invoice)).scalars().all()
        return [{"id": r.id, "tenant_id": r.tenant_id} for r in rows]
