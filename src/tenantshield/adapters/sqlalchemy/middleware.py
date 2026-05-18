"""SQLAlchemy adapter ASGI/WSGI middleware.

Provides ASGI and WSGI middleware classes that bind tenant context
to per-request scope using ``lifecycle.SessionScope`` internally.

Tenant resolution: middleware accepts a ``resolve_tenant`` callable
parameter. The ASGI variant accepts either synchronous resolvers (the
Phase 3B precedent) or asynchronous resolvers returning an awaitable
(Sub-fase 4A extension per Decision 3-A). The middleware auto-detects
the return type via ``inspect.iscoroutine`` and awaits when needed.
The WSGI variant remains synchronous-only (WSGI is inherently sync).

Example (synchronous resolver -- Phase 3B precedent)::

    from tenantshield.adapters.sqlalchemy import TenantSessionMiddleware

    def from_asgi_scope(scope):
        for name, value in scope.get('headers', []):
            if name == b'x-tenant-id':
                return value.decode('latin-1')
        return None

    asgi_app = TenantSessionMiddleware(app, resolve_tenant=from_asgi_scope)

Example (asynchronous resolver -- Sub-fase 4A extension)::

    async def from_asgi_scope_async(scope):
        # Fetch tenant from an async source (DB, cache, external API).
        async with some_async_client() as client:
            return await client.lookup_tenant(scope)

    asgi_app = TenantSessionMiddleware(app, resolve_tenant=from_asgi_scope_async)

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

import inspect
from typing import TYPE_CHECKING, Any, Literal

from tenantshield.adapters.sqlalchemy.lifecycle import SessionScope
from tenantshield.exceptions import MissingTenantContextError

_VALID_ON_MISSING = ("allow_unrestricted", "raise")
OnMissingTenant = Literal["allow_unrestricted", "raise"]

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

    ASGIScope = dict[str, Any]
    ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
    ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
    ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]
    ASGIResolveTenant = Callable[[ASGIScope], Any]

    WSGIEnviron = dict[str, Any]
    WSGIStartResponse = Callable[[str, list[tuple[str, str]]], Callable[..., None]]
    WSGIApp = Callable[[WSGIEnviron, WSGIStartResponse], Iterable[bytes]]
    WSGIResolveTenant = Callable[[WSGIEnviron], Any]


class TenantSessionMiddleware:
    """ASGI middleware binding tenant context per request.

    Wraps an ASGI application with tenant scope establishment for the
    duration of each HTTP request. Uses ``lifecycle.SessionScope``
    internally to bind tenant context via Python ``contextvars``.

    Context propagation across ``await`` boundaries is guaranteed by
    asyncio's per-task ``copy_context()`` semantics; sync
    ``SessionScope`` works correctly inside async middleware.
    Empirically validated in Tarea 3B.3 (sync resolver path) and
    Tarea 4A.0 Scenarios 1+2 (async resolver context propagation +
    cross-task isolation).

    Resolver dual-mode (Sub-fase 4A, Decision 3-A): ``resolve_tenant``
    may be either a synchronous callable returning ``TenantId | str |
    None`` (Phase 3B precedent) or an asynchronous callable returning
    an ``Awaitable[TenantId | str | None]``. The middleware invokes
    the callable, inspects the return value via
    ``inspect.iscoroutine``, and awaits when needed. Backward
    compatibility: existing synchronous resolvers continue to work
    unchanged.

    Example (synchronous resolver)::

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

    Example (asynchronous resolver)::

        async def resolve_tenant_async(scope):
            # Fetch tenant from an async source.
            async with db_pool.connection() as conn:
                return await conn.fetchval(
                    "SELECT tenant FROM sessions WHERE token = $1",
                    extract_token(scope),
                )

        app = TenantSessionMiddleware(
            asgi_app,
            resolve_tenant=resolve_tenant_async,
        )

    Lifecycle:

    1. ASGI app invokes middleware ``__call__(scope, receive, send)``.
    2. Middleware checks ``scope['type']``:
       - ``'http'``: invokes ``resolve_tenant(scope)`` (awaiting if
         coroutine) to extract tenant; wraps subsequent
         ``await self.app(...)`` with ``SessionScope(tenant=...)``.
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
            dict. Returns ``TenantId``, ``str``, or ``None``, or an
            awaitable yielding any of these (Sub-fase 4A). If the
            resolution result is ``None``, request proceeds without
            tenant scope binding (fall-through, per DR-022 standalone
            semantics; stricter behavior in Tarea 3B.5).

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
        on_missing_tenant: OnMissingTenant = "allow_unrestricted",
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
        if on_missing_tenant not in _VALID_ON_MISSING:
            msg = (
                f"on_missing_tenant must be 'allow_unrestricted' or 'raise', "
                f"got {on_missing_tenant!r}"
            )
            raise ValueError(msg)
        self.app = app
        self.resolve_tenant = resolve_tenant
        self.on_missing_tenant: OnMissingTenant = on_missing_tenant

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

        # Dual-mode resolver dispatch (Sub-fase 4A, Decision 3-A):
        # invoke resolver; if it returned a coroutine (async resolver),
        # await it. Synchronous resolvers (Phase 3B precedent) return
        # the value directly and skip the await.
        result = self.resolve_tenant(scope)
        tenant = await result if inspect.iscoroutine(result) else result

        if tenant is None and self.on_missing_tenant == "raise":
            raise MissingTenantContextError(
                operation="TenantSessionMiddleware.asgi",
                stack_context={
                    "hint": (
                        "Middleware configured with on_missing_tenant='raise' "
                        "but resolve_tenant returned None. Either return a "
                        "valid tenant from resolve_tenant or set "
                        "on_missing_tenant='allow_unrestricted'."
                    ),
                    "scope_type": scope.get("type"),
                    "scope_path": scope.get("path"),
                },
            )

        with SessionScope(tenant=tenant):
            await self.app(scope, receive, send)


class TenantSessionMiddlewareWSGI:
    """WSGI middleware binding tenant context per request.

    Wraps a WSGI application with tenant scope establishment for the
    duration of each request. Uses ``lifecycle.SessionScope``
    internally to bind tenant context.

    Generator-based response iteration (``yield from``) ensures
    ``SessionScope`` remains active during full response body
    iteration, NOT just during application invocation. Critical for
    streaming responses where adopter app yields chunks lazily.

    Empirically validated in Tarea 3B.4: a naive ``return self.app(...)``
    inside a ``with SessionScope(...)`` block exits scope BEFORE the
    caller iterates the response body. The ``yield from`` pattern
    makes ``__call__`` a generator that enters scope on first
    iteration and exits after the last chunk.

    Example::

        from tenantshield.adapters.sqlalchemy import (
            TenantSessionMiddlewareWSGI,
        )

        def resolve_tenant(environ):
            return environ.get("HTTP_X_TENANT_ID")

        app = TenantSessionMiddlewareWSGI(
            wsgi_app,
            resolve_tenant=resolve_tenant,
        )

    Adopters using Flask / Django (WSGI mode) / Gunicorn register
    via framework conventions::

        # Flask
        flask_app.wsgi_app = TenantSessionMiddlewareWSGI(
            flask_app.wsgi_app,
            resolve_tenant=resolve_tenant,
        )

        # Django (deployed via WSGI). In wsgi.py:
        from django.core.wsgi import get_wsgi_application
        application = TenantSessionMiddlewareWSGI(
            get_wsgi_application(),
            resolve_tenant=resolve_tenant,
        )

    WSGI environ header format: ``HTTP_<UPPERCASE_NAME>`` string
    keys with string values. Header ``X-Tenant-ID`` -> environ key
    ``HTTP_X_TENANT_ID``. Resolver callable receives raw environ
    dict.

    Args:
        app: The inner WSGI application to wrap.
        resolve_tenant: Callable that extracts tenant from WSGI
            environ dict. Returns ``TenantId``, ``str``, or
            ``None``. If ``None``, request proceeds without tenant
            scope binding (fall-through, per DR-022 standalone
            semantics; stricter behavior in Tarea 3B.5).

    Raises:
        TypeError: If ``resolve_tenant`` is not callable.

    Notes:
        For ASGI applications (FastAPI, Starlette), use
        ``TenantSessionMiddleware`` instead.

    See Also:
        ``TenantSessionMiddleware``: ASGI variant.
        ``SessionScope``: core context manager used internally.
        ``ADR-0008``: middleware lifecycle design pattern.
    """

    def __init__(
        self,
        app: WSGIApp,
        *,
        resolve_tenant: WSGIResolveTenant,
        on_missing_tenant: OnMissingTenant = "allow_unrestricted",
    ) -> None:
        if not callable(resolve_tenant):
            # Defensive runtime guard against type-system violations
            # (adopters bypassing type annotations); mypy considers
            # this unreachable per signature, but the check stays as
            # a foot-gun mitigation for dynamic / untyped callers.
            msg = (  # type: ignore[unreachable]
                f"resolve_tenant must be callable, got {type(resolve_tenant).__name__}"
            )
            raise TypeError(msg)
        if on_missing_tenant not in _VALID_ON_MISSING:
            msg = (
                f"on_missing_tenant must be 'allow_unrestricted' or 'raise', "
                f"got {on_missing_tenant!r}"
            )
            raise ValueError(msg)
        self.app = app
        self.resolve_tenant = resolve_tenant
        self.on_missing_tenant: OnMissingTenant = on_missing_tenant

    def __call__(
        self,
        environ: WSGIEnviron,
        start_response: WSGIStartResponse,
    ) -> Iterable[bytes]:
        """WSGI 1.0.1 entry point.

        Wraps the inner app with tenant scope binding. Uses
        ``yield from`` to keep ``SessionScope`` active during
        response body iteration -- critical for streaming responses
        where the inner app generates chunks lazily.
        """
        tenant = self.resolve_tenant(environ)

        if tenant is None and self.on_missing_tenant == "raise":
            raise MissingTenantContextError(
                operation="TenantSessionMiddlewareWSGI.wsgi",
                stack_context={
                    "hint": (
                        "Middleware configured with on_missing_tenant='raise' "
                        "but resolve_tenant returned None."
                    ),
                    "path": environ.get("PATH_INFO"),
                },
            )

        with SessionScope(tenant=tenant):
            yield from self.app(environ, start_response)
