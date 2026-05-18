"""Unit tests for middleware events emission (Sub-fase 5B.4).

Verifies the 2 middleware events emitted across 3 middleware variants:

- ``tenant.middleware.request_bound`` (DEBUG) -- emitted BEFORE scope ctx
  mgr enter when tenant resolved.
- ``tenant.middleware.request_unbound`` (DEBUG) -- emitted AFTER scope ctx
  mgr exit (in ``finally`` block) when tenant resolved.

Middleware variants covered:

- ``TenantSessionMiddleware`` (Phase 3B + 4A sync ASGI ctx mgr).
- ``AsyncTenantSessionMiddleware`` (Phase 5A async ctx mgr).
- ``TenantSessionMiddlewareWSGI`` (Phase 3B WSGI generator).

Fall-through case (tenant resolved as ``None`` with ``allow_unrestricted``)
emits NO middleware events (paralelo Tarea 5B.2 semantic). Emission order
canonical: ``middleware.request_bound`` -> ``scope.entered`` ->
``scope.exited`` -> ``middleware.request_unbound``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from structlog.testing import capture_logs

from tenantshield.adapters.sqlalchemy import (
    AsyncTenantSessionMiddleware,
    TenantSessionMiddleware,
    TenantSessionMiddlewareWSGI,
)
from tenantshield.observability import configure
from tenantshield.observability.events import (
    EVENT_MIDDLEWARE_REQUEST_BOUND,
    EVENT_MIDDLEWARE_REQUEST_UNBOUND,
    EVENT_SCOPE_ENTERED,
    EVENT_SCOPE_EXITED,
)

if TYPE_CHECKING:
    from collections.abc import Generator


_MIDDLEWARE_EVENTS = (EVENT_MIDDLEWARE_REQUEST_BOUND, EVENT_MIDDLEWARE_REQUEST_UNBOUND)


@pytest.fixture(autouse=True)
def _reset_observability() -> Generator[None, None, None]:
    configure(emit_events=False)
    yield
    configure(emit_events=False)


def _http_scope(headers: list[tuple[bytes, bytes]] | None = None) -> dict[str, Any]:
    return {"type": "http", "method": "GET", "path": "/", "headers": headers or []}


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b""}


async def _noop_send(_message: dict[str, Any]) -> None:
    return None


async def _noop_asgi_app(_scope: Any, _receive: Any, _send: Any) -> None:
    return None


def _noop_wsgi_app(_environ: Any, _start_response: Any) -> Generator[bytes, None, None]:
    yield b"body"


def _noop_start_response(_status: str, _headers: list[tuple[str, str]]) -> Any:
    return None


class TestSyncASGIMiddlewareEvents:
    """Verify ``TenantSessionMiddleware`` emits middleware events."""

    def test_bound_and_unbound_emitted_with_tenant(self) -> None:
        configure(emit_events=True)
        middleware = TenantSessionMiddleware(
            _noop_asgi_app,
            resolve_tenant=lambda _scope: "acme",
        )
        with capture_logs() as logs:
            asyncio.run(middleware(_http_scope(), _noop_receive, _noop_send))

        bound = [e for e in logs if e.get("event") == EVENT_MIDDLEWARE_REQUEST_BOUND]
        unbound = [e for e in logs if e.get("event") == EVENT_MIDDLEWARE_REQUEST_UNBOUND]

        assert len(bound) == 1
        assert bound[0]["tenant_id"] == "acme"
        assert bound[0]["middleware_class"] == "TenantSessionMiddleware"
        assert len(unbound) == 1
        assert unbound[0]["middleware_class"] == "TenantSessionMiddleware"

    def test_no_emission_on_fall_through(self) -> None:
        configure(emit_events=True)
        middleware = TenantSessionMiddleware(
            _noop_asgi_app,
            resolve_tenant=lambda _scope: None,
        )
        with capture_logs() as logs:
            asyncio.run(middleware(_http_scope(), _noop_receive, _noop_send))

        events = [e for e in logs if e.get("event") in _MIDDLEWARE_EVENTS]
        assert len(events) == 0

    def test_no_emission_when_disabled(self) -> None:
        configure(emit_events=False)
        middleware = TenantSessionMiddleware(
            _noop_asgi_app,
            resolve_tenant=lambda _scope: "acme",
        )
        with capture_logs() as logs:
            asyncio.run(middleware(_http_scope(), _noop_receive, _noop_send))

        events = [e for e in logs if e.get("event") in _MIDDLEWARE_EVENTS]
        assert len(events) == 0


class TestAsyncASGIMiddlewareEvents:
    """Verify ``AsyncTenantSessionMiddleware`` emits middleware events."""

    def test_bound_and_unbound_emitted_with_tenant(self) -> None:
        configure(emit_events=True)
        middleware = AsyncTenantSessionMiddleware(
            _noop_asgi_app,
            resolve_tenant=lambda _scope: "globex",
        )
        with capture_logs() as logs:
            asyncio.run(middleware(_http_scope(), _noop_receive, _noop_send))

        bound = [e for e in logs if e.get("event") == EVENT_MIDDLEWARE_REQUEST_BOUND]
        unbound = [e for e in logs if e.get("event") == EVENT_MIDDLEWARE_REQUEST_UNBOUND]

        assert len(bound) == 1
        assert bound[0]["tenant_id"] == "globex"
        assert bound[0]["middleware_class"] == "AsyncTenantSessionMiddleware"
        assert len(unbound) == 1
        assert unbound[0]["middleware_class"] == "AsyncTenantSessionMiddleware"

    def test_no_emission_on_fall_through(self) -> None:
        configure(emit_events=True)
        middleware = AsyncTenantSessionMiddleware(
            _noop_asgi_app,
            resolve_tenant=lambda _scope: None,
        )
        with capture_logs() as logs:
            asyncio.run(middleware(_http_scope(), _noop_receive, _noop_send))

        events = [e for e in logs if e.get("event") in _MIDDLEWARE_EVENTS]
        assert len(events) == 0


class TestWSGIMiddlewareEvents:
    """Verify ``TenantSessionMiddlewareWSGI`` emits middleware events."""

    def test_bound_and_unbound_emitted_with_tenant(self) -> None:
        configure(emit_events=True)
        middleware = TenantSessionMiddlewareWSGI(
            _noop_wsgi_app,
            resolve_tenant=lambda _env: "initech",
        )
        with capture_logs() as logs:
            list(middleware({}, _noop_start_response))

        bound = [e for e in logs if e.get("event") == EVENT_MIDDLEWARE_REQUEST_BOUND]
        unbound = [e for e in logs if e.get("event") == EVENT_MIDDLEWARE_REQUEST_UNBOUND]

        assert len(bound) == 1
        assert bound[0]["tenant_id"] == "initech"
        assert bound[0]["middleware_class"] == "TenantSessionMiddlewareWSGI"
        assert len(unbound) == 1
        assert unbound[0]["middleware_class"] == "TenantSessionMiddlewareWSGI"

    def test_no_emission_on_fall_through(self) -> None:
        configure(emit_events=True)
        middleware = TenantSessionMiddlewareWSGI(
            _noop_wsgi_app,
            resolve_tenant=lambda _env: None,
        )
        with capture_logs() as logs:
            list(middleware({}, _noop_start_response))

        events = [e for e in logs if e.get("event") in _MIDDLEWARE_EVENTS]
        assert len(events) == 0


class TestEmissionOrdering:
    """Verify canonical emission order: bound -> scope.entered -> scope.exited -> unbound."""

    def test_event_order_sync_asgi(self) -> None:
        configure(emit_events=True)
        middleware = TenantSessionMiddleware(
            _noop_asgi_app,
            resolve_tenant=lambda _scope: "acme",
        )
        with capture_logs() as logs:
            asyncio.run(middleware(_http_scope(), _noop_receive, _noop_send))

        relevant = [
            e["event"]
            for e in logs
            if e.get("event")
            in (
                EVENT_MIDDLEWARE_REQUEST_BOUND,
                EVENT_SCOPE_ENTERED,
                EVENT_SCOPE_EXITED,
                EVENT_MIDDLEWARE_REQUEST_UNBOUND,
            )
        ]
        assert relevant == [
            EVENT_MIDDLEWARE_REQUEST_BOUND,
            EVENT_SCOPE_ENTERED,
            EVENT_SCOPE_EXITED,
            EVENT_MIDDLEWARE_REQUEST_UNBOUND,
        ]

    def test_event_order_async_asgi(self) -> None:
        configure(emit_events=True)
        middleware = AsyncTenantSessionMiddleware(
            _noop_asgi_app,
            resolve_tenant=lambda _scope: "acme",
        )
        with capture_logs() as logs:
            asyncio.run(middleware(_http_scope(), _noop_receive, _noop_send))

        relevant = [
            e["event"]
            for e in logs
            if e.get("event")
            in (
                EVENT_MIDDLEWARE_REQUEST_BOUND,
                EVENT_SCOPE_ENTERED,
                EVENT_SCOPE_EXITED,
                EVENT_MIDDLEWARE_REQUEST_UNBOUND,
            )
        ]
        assert relevant == [
            EVENT_MIDDLEWARE_REQUEST_BOUND,
            EVENT_SCOPE_ENTERED,
            EVENT_SCOPE_EXITED,
            EVENT_MIDDLEWARE_REQUEST_UNBOUND,
        ]
