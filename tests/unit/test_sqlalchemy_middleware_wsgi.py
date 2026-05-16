"""Unit tests for SQLAlchemy adapter WSGI middleware.

Tests TenantSessionMiddlewareWSGI behavior:

- Request wraps with SessionScope.
- Resolve_tenant callable invoked with environ dict.
- Fall-through when resolve_tenant returns None.
- Exception propagation through middleware.
- Generator pattern keeps scope active during body iteration.
- Non-callable resolve_tenant rejected at construction.

Critical empirical finding (Tarea 3B.4): naive ``return self.app(...)``
inside ``with SessionScope(...)`` exits scope BEFORE iteration; the
implementation uses ``yield from`` to preserve scope through full
body iteration. The streaming test in
``TestTenantSessionMiddlewareWSGIGeneratorPattern`` is the load-bearing
verification of this design.

Per Decision 8-A: mock-based tests, no Flask/Werkzeug dependencies.
3C examples will validate against real WSGI frameworks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tenantshield import TenantId, try_current_tenant
from tenantshield.adapters.sqlalchemy import TenantSessionMiddlewareWSGI

if TYPE_CHECKING:
    from collections.abc import Iterable


def _make_environ(
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a minimal WSGI environ dict."""
    environ: dict[str, Any] = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/",
        "SERVER_NAME": "example.com",
        "SERVER_PORT": "8000",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
    }
    if headers:
        for name, value in headers.items():
            key = f"HTTP_{name.upper().replace('-', '_')}"
            environ[key] = value
    return environ


def _collect_response(body_iter: Iterable[bytes]) -> bytes:
    """Materialize WSGI response iterable into bytes."""
    return b"".join(body_iter)


def _start_response(_status: str, _headers: list[tuple[str, str]]) -> None:
    """No-op start_response callable for tests."""


class TestTenantSessionMiddlewareWSGIConstruction:
    """Verify middleware __init__ validation."""

    def test_non_callable_resolve_tenant_raises(self) -> None:
        def fake_app(_environ: Any, _start_response: Any) -> list[bytes]:
            return [b""]

        with pytest.raises(TypeError, match="must be callable"):
            TenantSessionMiddlewareWSGI(fake_app, resolve_tenant="not_callable")  # type: ignore[arg-type]


class TestTenantSessionMiddlewareWSGIRequestBinding:
    """Verify tenant binding for WSGI requests."""

    def test_request_with_resolved_tenant_binds_scope(self) -> None:
        captured_tenant: list[str | None] = []

        def inner_app(_environ: Any, start_response: Any) -> list[bytes]:
            ctx = try_current_tenant()
            captured_tenant.append(str(ctx.tenant_id) if ctx else None)
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"ok"]

        def resolver(environ: dict[str, Any]) -> str | None:
            return environ.get("HTTP_X_TENANT_ID")

        middleware = TenantSessionMiddlewareWSGI(inner_app, resolve_tenant=resolver)
        environ = _make_environ(headers={"X-Tenant-ID": "acme"})

        body = _collect_response(middleware(environ, _start_response))

        assert captured_tenant == ["acme"]
        assert body == b"ok"

    def test_request_with_none_resolver_falls_through(self) -> None:
        captured_tenant: list[str | None] = []

        def inner_app(_environ: Any, start_response: Any) -> list[bytes]:
            ctx = try_current_tenant()
            captured_tenant.append(str(ctx.tenant_id) if ctx else None)
            start_response("200 OK", [])
            return [b""]

        middleware = TenantSessionMiddlewareWSGI(inner_app, resolve_tenant=lambda _environ: None)

        _collect_response(middleware(_make_environ(), _start_response))

        assert captured_tenant == [None]


class TestTenantSessionMiddlewareWSGIGeneratorPattern:
    """Verify SessionScope persists during response body iteration.

    Critical: WSGI responses are iterables; if SessionScope exits
    before iteration completes, streaming responses lose tenant
    context for chunks generated lazily.
    """

    def test_scope_active_during_lazy_response_iteration(self) -> None:
        captured_per_chunk: list[str | None] = []

        def lazy_app(_environ: Any, start_response: Any) -> Iterable[bytes]:
            start_response("200 OK", [])
            ctx1 = try_current_tenant()
            captured_per_chunk.append(str(ctx1.tenant_id) if ctx1 else None)
            yield b"chunk1"
            ctx2 = try_current_tenant()
            captured_per_chunk.append(str(ctx2.tenant_id) if ctx2 else None)
            yield b"chunk2"

        middleware = TenantSessionMiddlewareWSGI(lazy_app, resolve_tenant=lambda _environ: "acme")

        body = _collect_response(middleware(_make_environ(), _start_response))

        assert captured_per_chunk == ["acme", "acme"]
        assert body == b"chunk1chunk2"


class TestTenantSessionMiddlewareWSGIExceptionPropagation:
    """Verify exceptions propagate and scope cleans up."""

    def test_inner_app_exception_propagates(self) -> None:
        def failing_app(_environ: Any, _start_response: Any) -> list[bytes]:
            msg = "simulated app error"
            raise RuntimeError(msg)

        middleware = TenantSessionMiddlewareWSGI(
            failing_app, resolve_tenant=lambda _environ: "acme"
        )

        with pytest.raises(RuntimeError, match="simulated"):
            _collect_response(middleware(_make_environ(), _start_response))

        assert try_current_tenant() is None


class TestTenantSessionMiddlewareWSGITenantIdAcceptance:
    """Verify resolve_tenant return types (TenantId, str, None)."""

    def test_resolver_returning_tenant_id_works(self) -> None:
        captured: list[str | None] = []

        def inner_app(_environ: Any, start_response: Any) -> list[bytes]:
            ctx = try_current_tenant()
            captured.append(str(ctx.tenant_id) if ctx else None)
            start_response("200 OK", [])
            return [b""]

        middleware = TenantSessionMiddlewareWSGI(
            inner_app, resolve_tenant=lambda _environ: TenantId("acme")
        )

        _collect_response(middleware(_make_environ(), _start_response))

        assert captured == ["acme"]
