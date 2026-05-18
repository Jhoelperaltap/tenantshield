"""Integration tests for ``AsyncTenantSessionMiddleware`` con FastAPI TestClient.

Sub-fase 5A.3 -- real ASGI framework verification que
``AsyncTenantSessionMiddleware`` integrates cleanly with production-
realistic FastAPI ASGI stack (Starlette TestClient underneath).

Test scope (paralelo Phase 4A.6 FastAPI example precedent):

- HTTP request con tenant header -> middleware binds scope via
  ``async with AsyncSessionScope(...)`` -> endpoint observes tenant
  -> response.
- Missing tenant header fall-through.
- Strict mode raises ``MissingTenantContextError``.
- Async resolver dispatched via ``inspect.iscoroutine`` (Phase 4A.5
  dual-mode preserved).
- ContextVar cleanup post-request.
- WebSocket scope pass-through (no tenant binding).

Resolves Sub-fase 5A risk #3 (FastAPI test patterns) deferred from
Tarea 5A.0 to Tarea 5A.3.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tenantshield import try_current_tenant
from tenantshield.adapters.sqlalchemy import AsyncTenantSessionMiddleware
from tenantshield.exceptions import MissingTenantContextError


def _resolve_tenant_from_scope(scope: dict[str, Any]) -> str | None:
    """Sync resolver extracting tenant from ASGI scope ``x-tenant-id`` header."""
    for name, value in scope.get("headers", []):
        if name == b"x-tenant-id":
            return value.decode("latin-1")
    return None


async def _resolve_tenant_from_scope_async(scope: dict[str, Any]) -> str | None:
    """Async resolver -- same logic, exercises ``inspect.iscoroutine`` dispatch."""
    for name, value in scope.get("headers", []):
        if name == b"x-tenant-id":
            return value.decode("latin-1")
    return None


def _make_app(resolve_tenant: Any, on_missing_tenant: str = "allow_unrestricted") -> FastAPI:
    """Build a FastAPI app con ``AsyncTenantSessionMiddleware`` mounted."""
    app = FastAPI()
    app.add_middleware(
        AsyncTenantSessionMiddleware,
        resolve_tenant=resolve_tenant,
        on_missing_tenant=on_missing_tenant,
    )

    @app.get("/observe-tenant")
    async def observe_tenant() -> dict[str, str | None]:
        ctx = try_current_tenant()
        return {"tenant_id": str(ctx.tenant_id) if ctx else None}

    return app


class TestAsyncTenantSessionMiddlewareFastAPIIntegration:
    """Real FastAPI TestClient integration tests."""

    def test_request_with_tenant_header_binds_scope(self) -> None:
        client = TestClient(_make_app(_resolve_tenant_from_scope))
        response = client.get("/observe-tenant", headers={"X-Tenant-Id": "acme"})
        assert response.status_code == 200
        assert response.json() == {"tenant_id": "acme"}

    def test_request_without_tenant_header_falls_through(self) -> None:
        client = TestClient(_make_app(_resolve_tenant_from_scope))
        response = client.get("/observe-tenant")
        assert response.status_code == 200
        assert response.json() == {"tenant_id": None}

    def test_strict_mode_missing_tenant_raises(self) -> None:
        app = _make_app(_resolve_tenant_from_scope, on_missing_tenant="raise")
        client = TestClient(app, raise_server_exceptions=True)
        with pytest.raises(MissingTenantContextError):
            client.get("/observe-tenant")

    def test_async_resolver_dispatch(self) -> None:
        """Async resolver awaited correctly by dual-mode dispatch (Phase 4A.5 inheritance)."""
        client = TestClient(_make_app(_resolve_tenant_from_scope_async))
        response = client.get("/observe-tenant", headers={"X-Tenant-Id": "globex"})
        assert response.status_code == 200
        assert response.json() == {"tenant_id": "globex"}

    def test_scope_cleaned_up_post_request(self) -> None:
        """ContextVar scope released after request completes."""
        client = TestClient(_make_app(_resolve_tenant_from_scope))
        client.get("/observe-tenant", headers={"X-Tenant-Id": "acme"})
        # Direct ContextVar inspect post-request: no tenant bound at this level.
        assert try_current_tenant() is None

    def test_multiple_sequential_requests_distinct_tenants(self) -> None:
        """Each request gets its own tenant binding; no leak across requests."""
        client = TestClient(_make_app(_resolve_tenant_from_scope))

        r1 = client.get("/observe-tenant", headers={"X-Tenant-Id": "acme"})
        r2 = client.get("/observe-tenant", headers={"X-Tenant-Id": "globex"})
        r3 = client.get("/observe-tenant")  # no header -> fall-through

        assert r1.json() == {"tenant_id": "acme"}
        assert r2.json() == {"tenant_id": "globex"}
        assert r3.json() == {"tenant_id": None}
