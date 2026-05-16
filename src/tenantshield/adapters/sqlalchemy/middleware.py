"""SQLAlchemy adapter ASGI/WSGI middleware.

Provides ASGI and WSGI middleware classes that bind tenant context
to per-request scope using ``lifecycle.SessionScope`` internally.

Tenant resolution: middleware accepts a ``resolve_tenant`` callable
parameter. Example::

    from tenantshield.adapters.sqlalchemy import TenantSessionMiddleware

    def from_asgi_scope(scope):
        for name, value in scope.get('headers', []):
            if name == b'x-tenant-id':
                return value.decode('latin-1')
        return None

    asgi_app = TenantSessionMiddleware(app, resolve_tenant=from_asgi_scope)

NO Phase 2B strategy reuse: Phase 2B ``TenantExtractionStrategy``
classes are Django-bound (use ``request.META``, ``request.get_host()``).
Cross-adapter strategy unification deferred per BLOCKER #30
resolution (post-empirical analysis in Sub-fase 3B Tarea 3B.0).
See ADR-0008.

Stricter read-without-scope enforcement (raise on missing tenant)
is opt-in via middleware configuration (Tarea 3B.5 + DR-026); the
default in this version is fall-through, preserving DR-022 semantics.

See ADR-0008 (middleware lifecycle design pattern).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tenantshield.adapters.sqlalchemy.lifecycle import SessionScope

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    ASGIScope = dict[str, Any]
    ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
    ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
    ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]
    ASGIResolveTenant = Callable[[ASGIScope], Any]


class TenantSessionMiddleware:
    """ASGI middleware binding tenant context per request.

    Wraps an ASGI application with tenant scope establishment for the
    duration of each HTTP request. Uses ``lifecycle.SessionScope``
    internally to bind tenant context via Python ``contextvars``.

    Context propagation across ``await`` boundaries is guaranteed by
    asyncio's per-task ``copy_context()`` semantics; sync
    ``SessionScope`` works correctly inside async middleware.
    Empirically validated in Tarea 3B.3.

    Example::

        from tenantshield.adapters.sqlalchemy import TenantSessionMiddleware

        def resolve_tenant(scope):
            for name, value in scope.get('headers', []):
                if name == b'x-tenant-id':
                    return value.decode('latin-1')
            return None

        app = TenantSessionMiddleware(
            asgi_app,
            resolve_tenant=resolve_tenant,
        )

    Lifecycle:

    1. ASGI app invokes middleware ``__call__(scope, receive, send)``.
    2. Middleware checks ``scope['type']``:
       - ``'http'``: invokes ``resolve_tenant(scope)`` to extract
         tenant; wraps subsequent ``await self.app(...)`` with
         ``SessionScope(tenant=...)``.
       - ``'websocket'`` or ``'lifespan'`` (or other): passes through
         without tenant binding. These contexts have no tenant
         semantics in this version.
    3. ``SessionScope`` exit happens after ``await self.app(...)``
       returns (success or exception), ensuring ContextVar cleanup.

    Adopters using FastAPI / Starlette / other ASGI frameworks
    register this middleware via framework conventions::

        # FastAPI
        app.add_middleware(TenantSessionMiddleware, resolve_tenant=...)

        # Starlette
        middlewares = [Middleware(TenantSessionMiddleware, resolve_tenant=...)]
        app = Starlette(middleware=middlewares)

    Args:
        app: The inner ASGI application to wrap.
        resolve_tenant: Callable that extracts tenant from ASGI scope
            dict. Returns ``TenantId``, ``str``, or ``None``. If
            ``None``, request proceeds without tenant scope binding
            (fall-through, per DR-022 standalone semantics; stricter
            behavior in Tarea 3B.5).

    Raises:
        TypeError: If ``resolve_tenant`` is not callable.

    See Also:
        ``SessionScope``: core context manager used internally.
        ``bind_session_to_tenant``: explicit binding helper for
            non-middleware contexts.
        ``ADR-0008``: middleware lifecycle design pattern.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        resolve_tenant: ASGIResolveTenant,
    ) -> None:
        if not callable(resolve_tenant):
            # Defensive runtime guard against type-system violations
            # (adopters bypassing type annotations); mypy considers this
            # unreachable per signature, but the check stays as a
            # foot-gun mitigation for dynamic / untyped callers.
            msg = (  # type: ignore[unreachable]
                f"resolve_tenant must be callable, got {type(resolve_tenant).__name__}"
            )
            raise TypeError(msg)
        self.app = app
        self.resolve_tenant = resolve_tenant

    async def __call__(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """ASGI 3.0 entry point.

        Wraps the inner app with tenant scope binding for HTTP
        requests. Pass-through for websocket / lifespan / other scope
        types.
        """
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        tenant = self.resolve_tenant(scope)

        with SessionScope(tenant=tenant):
            await self.app(scope, receive, send)
