"""End-to-end tests for AsyncSession-native FastAPI + TenantShield example.

Validates Phase 4A Decision 7-A: existing FastAPI sync example replaced
with AsyncSession-native canonical pattern. Sub-fase 4A integration
verified empirically:

- ``TenantSessionMiddleware`` dual-mode resolver capability (default
  ``app`` uses sync resolver; ``strict_app`` uses async resolver).
- ``Depends(get_async_session)`` + ``AsyncSession`` consumed directly
  (no threadpool wrap).
- Phase 3A ``do_orm_execute`` event handler reuse filters
  ``await session.execute(select(...))`` by active tenant scope.

Test discovery: ``conftest.py`` at the example root adds the example
directory to ``sys.path`` so ``from app import ...`` resolves.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import app, strict_app
from tenantshield.exceptions import MissingTenantContextError


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def strict_client() -> TestClient:
    return TestClient(strict_app, raise_server_exceptions=True)


class TestFastAPIAsyncSessionIntegration:
    """Verify ASGI middleware + AsyncSession + Phase 3A enforcement integration."""

    def test_async_route_returns_only_acme_invoices(self, client: TestClient) -> None:
        response = client.get("/invoices", headers={"X-Tenant-ID": "acme"})
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 2
        assert all(r["tenant_id"] == "acme" for r in rows)

    def test_async_route_returns_only_globex_invoices(self, client: TestClient) -> None:
        response = client.get("/invoices", headers={"X-Tenant-ID": "globex"})
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 1
        assert all(r["tenant_id"] == "globex" for r in rows)

    def test_no_header_default_mode_falls_through(self, client: TestClient) -> None:
        """Default ``allow_unrestricted`` mode: no header -> no filtering (DR-022)."""
        response = client.get("/invoices")
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 3  # 2 acme + 1 globex


class TestFastAPIAsyncResolverStrictMode:
    """Verify ``on_missing_tenant='raise'`` strict mode with async resolver."""

    def test_strict_mode_async_resolver_with_tenant_proceeds(
        self, strict_client: TestClient
    ) -> None:
        """Async resolver returning a tenant id under strict mode: request proceeds."""
        response = strict_client.get("/invoices", headers={"X-Tenant-ID": "acme"})
        assert response.status_code == 200
        rows = response.json()
        assert all(r["tenant_id"] == "acme" for r in rows)

    def test_strict_mode_async_resolver_with_globex_proceeds(
        self, strict_client: TestClient
    ) -> None:
        """Async resolver returning globex under strict mode: request proceeds."""
        response = strict_client.get("/invoices", headers={"X-Tenant-ID": "globex"})
        assert response.status_code == 200
        rows = response.json()
        assert all(r["tenant_id"] == "globex" for r in rows)

    def test_strict_mode_async_resolver_without_tenant_raises(
        self, strict_client: TestClient
    ) -> None:
        """Async resolver returning None under strict mode: MissingTenantContextError propagates."""
        with pytest.raises(MissingTenantContextError):
            strict_client.get("/invoices")
