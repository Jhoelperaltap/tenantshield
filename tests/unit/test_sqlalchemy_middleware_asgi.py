"""Unit tests for SQLAlchemy adapter ASGI middleware.

Tests TenantSessionMiddleware ASGI behavior:

- HTTP request wraps with SessionScope.
- Non-HTTP scopes (websocket, lifespan) pass through.
- Resolve_tenant callable invoked with scope dict.
- Fall-through when resolve_tenant returns None.
- Exception propagation through middleware.
- ContextVar propagation across await boundaries.
- Non-callable resolve_tenant rejected at construction.

Per Decision 8-A: mock-based tests, no Starlette/Uvicorn dependencies.
3C examples will validate against real ASGI frameworks.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from tenantshield import TenantId, try_current_tenant
from tenantshield.adapters.sqlalchemy import TenantSessionMiddleware
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


class TestTenantSessionMiddlewareConstruction:
    """Verify middleware __init__ validation."""

    def test_non_callable_resolve_tenant_raises(self) -> None:
        async def fake_app(_scope: Any, _receive: Any, _send: Any) -> None:
            pass

        with pytest.raises(TypeError, match="must be callable"):
            TenantSessionMiddleware(fake_app, resolve_tenant="not_callable")  # type: ignore[arg-type]


class TestTenantSessionMiddlewareHTTPScope:
    """Verify tenant binding for HTTP scope."""

    def test_http_with_resolved_tenant_binds_scope(self) -> None:
        captured_tenant: list[str | None] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx = try_current_tenant()
            captured_tenant.append(str(ctx.tenant_id) if ctx else None)

        def resolver(scope: dict[str, Any]) -> str | None:
            for name, value in scope.get("headers", []):
                if name == b"x-tenant-id":
                    return value.decode("latin-1")
            return None

        middleware = TenantSessionMiddleware(inner_app, resolve_tenant=resolver)
        scope = _make_http_scope(headers=[(b"x-tenant-id", b"acme")])

        async def run() -> None:
            _, send = _make_send()
            await middleware(scope, _noop_receive, send)

        asyncio.run(run())

        assert captured_tenant == ["acme"]

    def test_http_with_none_resolver_falls_through(self) -> None:
        captured_tenant: list[str | None] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx = try_current_tenant()
            captured_tenant.append(str(ctx.tenant_id) if ctx else None)

        middleware = TenantSessionMiddleware(inner_app, resolve_tenant=lambda _scope: None)

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)

        asyncio.run(run())

        assert captured_tenant == [None]


class TestTenantSessionMiddlewareNonHTTPScope:
    """Verify non-HTTP scopes pass through without tenant binding."""

    def test_websocket_scope_passes_through(self) -> None:
        captured_tenant: list[str | None] = []
        resolver_called: list[bool] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx = try_current_tenant()
            captured_tenant.append(str(ctx.tenant_id) if ctx else None)

        def resolver(_scope: dict[str, Any]) -> str:
            resolver_called.append(True)
            return "should_not_be_used"

        middleware = TenantSessionMiddleware(inner_app, resolve_tenant=resolver)

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_websocket_scope(), _noop_receive, send)

        asyncio.run(run())

        assert resolver_called == []
        assert captured_tenant == [None]

    def test_lifespan_scope_passes_through(self) -> None:
        captured_tenant: list[str | None] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx = try_current_tenant()
            captured_tenant.append(str(ctx.tenant_id) if ctx else None)

        middleware = TenantSessionMiddleware(inner_app, resolve_tenant=lambda _scope: "ignored")

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_lifespan_scope(), _noop_receive, send)

        asyncio.run(run())

        assert captured_tenant == [None]


class TestTenantSessionMiddlewareContextPropagation:
    """Verify ContextVar propagates across await boundaries."""

    def test_tenant_visible_after_await_inside_app(self) -> None:
        captured_tenant: list[str | None] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx1 = try_current_tenant()
            captured_tenant.append(str(ctx1.tenant_id) if ctx1 else None)

            await asyncio.sleep(0)

            ctx2 = try_current_tenant()
            captured_tenant.append(str(ctx2.tenant_id) if ctx2 else None)

        middleware = TenantSessionMiddleware(inner_app, resolve_tenant=lambda _scope: "acme")

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)

        asyncio.run(run())

        assert captured_tenant == ["acme", "acme"]


class TestTenantSessionMiddlewareExceptionPropagation:
    """Verify exceptions propagate and scope cleans up."""

    def test_inner_app_exception_propagates(self) -> None:
        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            msg = "simulated app error"
            raise RuntimeError(msg)

        middleware = TenantSessionMiddleware(inner_app, resolve_tenant=lambda _scope: "acme")

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)

        with pytest.raises(RuntimeError, match="simulated"):
            asyncio.run(run())

        assert try_current_tenant() is None


class TestTenantSessionMiddlewareTenantIdAcceptance:
    """Verify resolve_tenant return types (TenantId, str, None)."""

    def test_resolver_returning_tenant_id_works(self) -> None:
        captured: list[str | None] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx = try_current_tenant()
            captured.append(str(ctx.tenant_id) if ctx else None)

        middleware = TenantSessionMiddleware(
            inner_app, resolve_tenant=lambda _scope: TenantId("acme")
        )

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)

        asyncio.run(run())

        assert captured == ["acme"]


class TestTenantSessionMiddlewareStrictMode:
    """Verify on_missing_tenant strict enforcement (ASGI). DR-026."""

    def test_default_mode_is_allow_unrestricted(self) -> None:
        """Default behavior fall-through preserved (DR-022 backwards-compat)."""
        captured: list[str | None] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx = try_current_tenant()
            captured.append(str(ctx.tenant_id) if ctx else None)

        middleware = TenantSessionMiddleware(inner_app, resolve_tenant=lambda _scope: None)

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)

        asyncio.run(run())

        assert captured == [None]

    def test_strict_mode_raises_on_none_tenant(self) -> None:
        """on_missing_tenant='raise' triggers MissingTenantContextError."""

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            pass

        middleware = TenantSessionMiddleware(
            inner_app,
            resolve_tenant=lambda _scope: None,
            on_missing_tenant="raise",
        )

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)

        with pytest.raises(MissingTenantContextError) as exc_info:
            asyncio.run(run())

        assert "TenantSessionMiddleware" in exc_info.value.operation

    def test_strict_mode_with_valid_tenant_proceeds(self) -> None:
        """Strict mode + valid tenant: middleware proceeds normally."""
        captured: list[str | None] = []

        async def inner_app(_scope: Any, _receive: Any, _send: Any) -> None:
            ctx = try_current_tenant()
            captured.append(str(ctx.tenant_id) if ctx else None)

        middleware = TenantSessionMiddleware(
            inner_app,
            resolve_tenant=lambda _scope: "acme",
            on_missing_tenant="raise",
        )

        async def run() -> None:
            _, send = _make_send()
            await middleware(_make_http_scope(), _noop_receive, send)

        asyncio.run(run())

        assert captured == ["acme"]

    def test_invalid_on_missing_tenant_value_raises(self) -> None:
        """Construction validates on_missing_tenant value."""

        async def fake_app(_scope: Any, _receive: Any, _send: Any) -> None:
            pass

        with pytest.raises(ValueError, match="on_missing_tenant must be"):
            TenantSessionMiddleware(
                fake_app,
                resolve_tenant=lambda _scope: None,
                on_missing_tenant="invalid_value",  # type: ignore[arg-type]
            )
