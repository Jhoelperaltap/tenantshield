"""SQLAlchemy adapter async session lifecycle management.

Provides framework-agnostic abstractions for binding tenant context to
SQLAlchemy ``AsyncSession`` lifecycle, parallel to ``lifecycle.py`` for
sync ``Session`` usage:

- ``AsyncSessionScope``: async context manager binding tenant scope
  around ``AsyncSession`` operations.

Used as the core abstraction for ASGI integrations and any async code
path performing ``AsyncSession`` operations (background async tasks,
async CLI tools, custom async integrations).

Decision 3-A (Phase 4 kickoff): parallel API surface. Adopters pick
sync or async helper based on their Session flavor; no dual-mode
magic. Sync ``SessionScope`` and ``AsyncSessionScope`` are distinct,
independent context managers sharing the same underlying ContextVar
primitives (``bind_tenant`` + ``atenant_scope``).

AsyncSession event listener integration is automatic. Phase 3A
``events.py`` registers ``do_orm_execute`` on ``Session``; SQLAlchemy
routes ``AsyncSession`` operations through ``AsyncSession``
``.sync_session_class`` (= ``Session``), so the same registration
fires for both sync and async dispatch paths. Empirically validated
in Tarea 4A.0 Scenarios 3 (``do_orm_execute`` under
``AsyncSession.execute``) and 4 (mapper events under
``await session.flush()``). No additional event listener registration
is required for ``AsyncSession`` enforcement.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from tenantshield import TenantId, bind_tenant
from tenantshield import atenant_scope as _atenant_scope

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable


@asynccontextmanager
async def AsyncSessionScope(  # noqa: N802 -- async context manager presents as class-like to adopters
    tenant: TenantId | str | None = None,
    *,
    resolve_tenant: Callable[[], TenantId | str | None] | None = None,
) -> AsyncGenerator[None, None]:
    """Bind tenant context around a block of SQLAlchemy AsyncSession operations.

    Parallel to :func:`tenantshield.adapters.sqlalchemy.SessionScope` for
    sync ``Session`` usage. Use within ASGI route handlers or any async
    code path that performs SQLAlchemy ``AsyncSession`` operations.

    Two usage patterns:

    1. **Direct tenant binding** (``tenant`` parameter)::

        async with AsyncSessionScope(tenant="acme"):
            async with async_session() as s:
                await s.execute(select(Invoice))

    2. **Callable resolver** (``resolve_tenant`` parameter)::

        def from_env():
            return os.environ.get("TENANT_ID")

        async with AsyncSessionScope(resolve_tenant=from_env):
            async with async_session() as s:
                ...

    Behavior:

    - If ``tenant`` is provided: bind that tenant for the scope's
      duration.
    - Else if ``resolve_tenant`` is provided: invoke it; bind result
      if non-None, fall through if None.
    - If both are None or resolver returns None: fall-through (no
      scope bound). Caller can still operate; SA adapter standalone
      semantics apply per DR-022.

    Exception handling: standard async context manager semantics.
    Exceptions inside the ``async with`` block propagate transparently;
    scope cleanup happens via ``atenant_scope`` (Tarea 4A.0 Scenario 1
    verified ContextVar reset across await + Scenario 6 verified async
    ctx mgr nesting composition).

    Concurrency safety: ``asyncio.gather`` tasks each receive
    ``copy_context()`` per asyncio semantics; tenant bound in one task
    does not leak to concurrent tasks (Tarea 4A.0 Scenario 2
    empirically validated). Safe for multi-tenant request handling
    under high concurrency.

    The ``resolve_tenant`` callable must be synchronous for this
    helper. Async resolver semantics (callable returning ``Awaitable``)
    are deferred to Tarea 4A.5 ASGI middleware integration, where they
    compose naturally with the request lifecycle. Adopters who need to
    resolve a tenant from an async source within a custom async block
    should perform the resolution before entering the scope::

        tenant = await fetch_tenant_from_db()
        async with AsyncSessionScope(tenant=tenant):
            ...

    Args:
        tenant: Optional tenant identifier. Can be ``TenantId`` or
            ``str`` (normalized internally). Mutually exclusive with
            ``resolve_tenant``.
        resolve_tenant: Optional synchronous callable returning
            ``TenantId``, ``str``, or ``None``. Invoked at scope entry.
            Mutually exclusive with ``tenant``.

    Yields:
        None. Tenant scope is bound via ``atenant_scope`` internally;
        adopters call ``try_current_tenant()`` inside the block to
        inspect the active context.

    Raises:
        ValueError: If both ``tenant`` and ``resolve_tenant`` are
            provided.

    See Also:
        :func:`SessionScope` -- synchronous ``Session`` equivalent.
        ``tenantshield.atenant_scope`` -- Phase 1 async core API.
    """
    if tenant is not None and resolve_tenant is not None:
        msg = (
            "AsyncSessionScope accepts either 'tenant' or "
            "'resolve_tenant', not both. Use 'tenant' for direct "
            "binding or 'resolve_tenant' for callable resolution."
        )
        raise ValueError(msg)

    resolved: TenantId | str | None = None
    if tenant is not None:
        resolved = tenant
    elif resolve_tenant is not None:
        resolved = resolve_tenant()

    if resolved is None:
        # Fall-through: no scope bound. SA adapter standalone semantics
        # apply per DR-022. Adopters opting into stricter behavior
        # configure middleware on_missing_tenant='raise' (DR-026).
        yield
        return

    # TenantId is a NewType over str (identity at runtime). Normalize
    # via str() to accept both bare strings and NewType-tagged values
    # per Rule 53.
    tenant_id = TenantId(str(resolved))
    ctx = bind_tenant(tenant_id)
    async with _atenant_scope(ctx):
        yield
