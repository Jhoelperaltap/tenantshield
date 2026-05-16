"""SQLAlchemy adapter session lifecycle management.

Provides framework-agnostic abstractions for binding tenant context
to SQLAlchemy ``Session`` lifecycle:

- ``SessionScope``: context manager binding tenant scope around
  session operations.
- ``bind_session_to_tenant()``: helper invoked at session
  initialization (added in Tarea 3B.2).

Used as the core abstraction underlying ``middleware.py`` ASGI/WSGI
wrappers. Adopters can use ``SessionScope`` directly in any context
(CLI, background workers, custom integration).

Tenant resolution accepts callable resolvers, NOT Phase 2B strategy
classes (which are Django-bound). Cross-adapter strategy unification
deferred per BLOCKER #30 resolution; see ADR-0008 (forward reference;
materialization post-Tarea 3B.2).

Decision 5-B (Phase 3B kickoff): ContextVar-based binding, NOT
SQLAlchemy Session subclassing. Allows composition with arbitrary
``sessionmaker`` / ``scoped_session`` patterns without inheritance.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from tenantshield import TenantId, bind_tenant
from tenantshield import tenant_scope as _tenant_scope

if TYPE_CHECKING:
    from collections.abc import Callable, Generator


@contextmanager
def SessionScope(  # noqa: N802 -- context manager presents as class-like to adopters
    tenant: TenantId | str | None = None,
    *,
    resolve_tenant: Callable[[], TenantId | str | None] | None = None,
) -> Generator[None, None, None]:
    """Bind tenant context around a block of SQLAlchemy operations.

    ``SessionScope`` is a context manager that establishes (or skips)
    a tenant scope for the duration of the ``with`` block. It is a
    thin wrapper around ``tenantshield.tenant_scope`` with optional
    callable-based tenant resolution.

    Two usage patterns:

    1. **Direct tenant binding** (``tenant`` parameter)::

        with SessionScope(tenant="acme"):
            with Session(engine) as s:
                s.add(Invoice(amount=100))
                s.commit()

    2. **Callable resolver** (``resolve_tenant`` parameter)::

        def from_env():
            return os.environ.get("TENANT_ID")

        with SessionScope(resolve_tenant=from_env):
            with Session(engine) as s:
                ...

    Behavior:

    - If ``tenant`` is provided: bind that tenant for the scope's
      duration.
    - Else if ``resolve_tenant`` is provided: invoke it; bind result
      if non-None, fall through if None.
    - If both are None or resolver returns None: fall-through (no
      scope bound). Caller can still operate; SA adapter standalone
      semantics apply per DR-022.

    Exception handling: standard context manager semantics. Exceptions
    inside the ``with`` block propagate transparently; scope cleanup
    happens via ``tenant_scope`` (verified empirically in Tarea
    3B.0-re Scenario 2).

    Args:
        tenant: Optional tenant identifier. Can be ``TenantId`` or
            ``str`` (normalized internally). Mutually exclusive with
            ``resolve_tenant``.
        resolve_tenant: Optional callable returning ``TenantId``,
            ``str``, or ``None``. Invoked at scope entry. Mutually
            exclusive with ``tenant``.

    Yields:
        None. Tenant scope is bound via ``tenant_scope`` internally;
        adopters call ``try_current_tenant()`` inside the block to
        inspect the active context.

    Raises:
        ValueError: If both ``tenant`` and ``resolve_tenant`` are
            provided.

    See Also:
        ``tenantshield.tenant_scope``: Phase 1 core API.
        ``middleware.TenantSessionMiddleware``: ASGI/WSGI wrapper
        (Tarea 3B.3/3B.4).
    """
    if tenant is not None and resolve_tenant is not None:
        msg = (
            "SessionScope accepts either 'tenant' or 'resolve_tenant', "
            "not both. Use 'tenant' for direct binding or "
            "'resolve_tenant' for callable resolution."
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
        # configure middleware on_missing_tenant='raise' (DR-026 in 3B.5).
        yield
        return

    # TenantId is a NewType over str (identity at runtime). Normalize via
    # str() to accept both bare strings and NewType-tagged values.
    tenant_id = TenantId(str(resolved))
    ctx = bind_tenant(tenant_id)
    with _tenant_scope(ctx):
        yield


@contextmanager
def bind_session_to_tenant(
    tenant: TenantId | str | None,
) -> Generator[None, None, None]:
    """Explicitly bind a session-scoped tenant for SQLAlchemy operations.

    Helper for adopters who need explicit tenant binding without the
    callable-resolver flexibility of ``SessionScope``. Use cases:

    - CLI scripts where tenant is determined from command-line args.
    - Background workers processing tenant-specific jobs.
    - Test fixtures with hardcoded tenant scopes.

    Composable with ``SessionScope``: invoking
    ``bind_session_to_tenant`` inside an active ``SessionScope`` block
    creates a nested scope (inner tenant overrides outer; outer
    restored on inner exit). Empirically validated in Tarea 3B.2.

    Direct usage::

        with bind_session_to_tenant("acme"):
            with Session(engine) as s:
                # All SA operations enforced with acme tenant
                ...

    Composition with SessionScope::

        with SessionScope(resolve_tenant=from_request):
            with bind_session_to_tenant("system_admin"):
                # Override resolved tenant for specific block
                ...

    Difference from ``SessionScope``:

    - ``SessionScope``: callable resolver + fall-through support.
    - ``bind_session_to_tenant``: direct tenant only, no fall-through.

    Both ultimately wrap ``tenantshield.tenant_scope``. Choose based
    on whether tenant resolution is callable-driven (``SessionScope``)
    or determined-up-front (``bind_session_to_tenant``).

    Args:
        tenant: Tenant identifier. Required, non-empty. Can be
            ``TenantId`` or ``str`` (normalized internally via
            ``TenantId(str(tenant))``). Type allows ``None`` for
            adopter ergonomic safety (dynamic code might pass None);
            None / empty raise ``ValueError`` with helpful guidance
            toward ``SessionScope`` for fall-through use cases.

    Yields:
        None. Tenant scope is bound via ``tenant_scope`` internally;
        adopters call ``try_current_tenant()`` to inspect.

    Raises:
        ValueError: If ``tenant`` is ``None`` or evaluates to empty
            after string conversion. Helpful message points to
            ``SessionScope`` as alternative for fall-through use cases.

    See Also:
        ``SessionScope``: more flexible context manager with resolver
            callable support and fall-through semantics.
        ``tenantshield.tenant_scope``: Phase 1 core API.
    """
    if tenant is None or not str(tenant):
        msg = (
            "bind_session_to_tenant requires a non-empty tenant. "
            "For fall-through behavior (no scope bound), use "
            "SessionScope with no arguments or resolve_tenant "
            "returning None."
        )
        raise ValueError(msg)

    tenant_id = TenantId(str(tenant))
    ctx = bind_tenant(tenant_id)
    with _tenant_scope(ctx):
        yield
