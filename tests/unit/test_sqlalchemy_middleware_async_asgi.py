"""Unit tests for SQLAlchemy adapter ASGI-native async middleware (Sub-fase 5A.1).

Tests :class:`AsyncTenantSessionMiddleware` behavior:

- HTTP request wraps with ``async with AsyncSessionScope(...)``.
- Non-HTTP scopes (websocket, lifespan) pass through.
- Sync + async resolver dispatch (paralelo Phase 4A.5 dual-mode).
- Fall-through when resolve_tenant returns None.
- Strict mode raises MissingTenantContextError.
- Concurrent ``asyncio.gather`` request isolation.
- Construction validation (callable + on_missing_tenant).

Mock-based tests per Phase 4A.5 precedent (no Starlette/Uvicorn
dependencies). Real ASGI framework integration verified vía Sub-fase
5A.3 examples integration.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from tenantshield import try_current_tenant
from tenantshield.adapters.sqlalchemy import AsyncTenantSessionMiddleware
from tenantshield.exceptions import MissingTenantContextError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def _make_http_scope(
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict[str, Any]:
    """Build a minimal ASGI HTTP scope dict."""
    return {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
    }


def _make_websocket_scope() -> dict[str, Any]:
    """Build a minimal ASGI WebSocket scope dict."""
    return {"type": "websocket", "path": "/ws"}


def _make_lifespan_scope() -> dict[str, Any]:
    """Build a minimal ASGI lifespan scope dict."""
    return {"type": "lifespan"}


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b""}


def _make_send() -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], Awaitable[None]]]:
    """Build a send callable that collects messages."""
    messages: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    return messages, send


class TestAsyncTenantSessionMiddlewareConstruction:
    """Verify middleware ``__init__`` validation."""

    def test_non_callable_resolve_tenant_raises(self) -> None:
        async def fake_app(_scope: Any, _receive: Any, _send: Any) -> None:
            pass

        with pytest.raises(TypeError, match="must be callable"):
            AsyncTenantSessionMiddleware(fake_app, resolve_tenant="not_callable")  # type: ignore[arg-type]

    def test_invalid_on_missing_tenant_value_raises(self) -> None:
        async def fake_app(_scope: Any, _receive: Any, _send: Any) -> None:
            pass

        with pytest.raises(ValueError, match="on_missing_tenant must be"):
            AsyncTenantSessionMiddleware(
                fake_app,
                resolve_tenant=lambda _scope: None,
                on_missing_tenant="invalid_value",  # type: ignore[arg-type]
            )


class TestAsyncTenantSessionMiddlewareHTTPScope:
    """Verify HTTP scope dispatch + tenant binding."""

    def test_http_with_sync_resolver_binds_scope(self) -> None:
        captured_tenant: list[str | None] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx = try_current_tenant()
            captured_tenant.append(str(ctx.tenant_id) if ctx else None)

        def resolver(scope: dict[str, Any]) -> str | None:
            for name, value in scope.get("headers", []):
                if name == b"x-tenant-id":
                    return value.decode("latin-1")
            return None

        middleware = AsyncTenantSessionMiddleware(inner_app, resolve_tenant=resolver)
        scope = _make_http_scope(headers=[(b"x-tenant-id", b"acme")])

        async def run() -> None:
            _, send = _make_send()
            await middleware(scope, _noop_receive, send)

        asyncio.run(run())

        assert captured_tenant == ["acme"]

    def test_http_with_async_resolver_binds_scope(self) -> None:
        captured_tenant: list[str | None] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx = try_current_tenant()
            captured_tenant.append(str(ctx.tenant_id) if ctx else None)

        async def async_resolver(scope: dict[str, Any]) -> str | None:
            for name, value in scope.get("headers", []):
                if name == b"x-tenant-id":
                    return value.decode("latin-1")
            return None

        middleware = AsyncTenantSessionMiddleware(inner_app, resolve_tenant=async_resolver)
        scope = _make_http_scope(headers=[(b"x-tenant-id", b"globex")])

        async def run() -> None:
            _, send = _make_send()
            await middleware(scope, _noop_receive, send)

        asyncio.run(run())

        assert captured_tenant == ["globex"]

    def test_http_with_none_resolver_falls_through(self) -> None:
        captured_tenant: list[str | None] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx = try_current_tenant()
            captured_tenant.append(str(ctx.tenant_id) if ctx else None)

        middleware = AsyncTenantSessionMiddleware(
            inner_app,
            resolve_tenant=lambda _scope: None,
        )

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)

        asyncio.run(run())

        assert captured_tenant == [None]

    def test_http_with_none_strict_mode_raises(self) -> None:
        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            pass

        middleware = AsyncTenantSessionMiddleware(
            inner_app,
            resolve_tenant=lambda _scope: None,
            on_missing_tenant="raise",
        )

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)

        with pytest.raises(MissingTenantContextError):
            asyncio.run(run())


class TestAsyncTenantSessionMiddlewareNonHTTPScopes:
    """Verify non-HTTP scope pass-through."""

    def test_websocket_scope_passes_through_without_binding(self) -> None:
        captured_tenant: list[str | None] = []
        inner_called: list[bool] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            inner_called.append(True)
            ctx = try_current_tenant()
            captured_tenant.append(str(ctx.tenant_id) if ctx else None)

        def resolver(_scope: dict[str, Any]) -> str:
            return "should_not_be_bound"

        middleware = AsyncTenantSessionMiddleware(inner_app, resolve_tenant=resolver)

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_websocket_scope(), _noop_receive, send)

        asyncio.run(run())

        assert inner_called == [True]
        # No tenant bound during WebSocket scope (pass-through).
        assert captured_tenant == [None]

    def test_lifespan_scope_passes_through_without_binding(self) -> None:
        inner_called: list[bool] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            inner_called.append(True)

        middleware = AsyncTenantSessionMiddleware(
            inner_app,
            resolve_tenant=lambda _scope: "ignored",
        )

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_lifespan_scope(), _noop_receive, send)

        asyncio.run(run())

        assert inner_called == [True]


class TestAsyncTenantSessionMiddlewareCleanup:
    """Verify ContextVar scope cleanup after request."""

    def test_scope_cleaned_up_after_http_request(self) -> None:
        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            pass

        middleware = AsyncTenantSessionMiddleware(
            inner_app,
            resolve_tenant=lambda _scope: "acme",
        )

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)
            # Verify scope cleaned up post-middleware
            assert try_current_tenant() is None

        asyncio.run(run())


class TestAsyncTenantSessionMiddlewareConcurrentIsolation:
    """Verify concurrent ``asyncio.gather`` request isolation."""

    def test_gather_concurrent_requests_isolated(self) -> None:
        """Multiple concurrent HTTP requests con distinct tenants -- no leak."""
        captured: dict[str, list[str | None]] = {}

        def make_inner_app(label: str) -> Callable[[Any, Any, Any], Awaitable[None]]:
            captured[label] = []

            async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
                ctx = try_current_tenant()
                captured[label].append(str(ctx.tenant_id) if ctx else None)

            return inner_app

        async def one_request(label: str, tenant: str) -> None:
            middleware = AsyncTenantSessionMiddleware(
                make_inner_app(label),
                resolve_tenant=lambda _s, _t=tenant: _t,
            )
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)

        async def run() -> None:
            await asyncio.gather(
                one_request("acme", "acme"),
                one_request("globex", "globex"),
                one_request("initech", "initech"),
            )

        asyncio.run(run())

        assert captured["acme"] == ["acme"]
        assert captured["globex"] == ["globex"]
        assert captured["initech"] == ["initech"]
