"""End-to-end tests for FastAPI + TenantShield example.

Validates Sub-fase 3B middleware against a real FastAPI app
(Decision 8-A from Phase 3B kickoff: mock-based tests in 3B are
validated against real frameworks in 3C examples).

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


class TestFastAPIIntegration:
    """Verify ASGI middleware + SA enforcement integration."""

    def test_sync_route_returns_only_acme_invoices(self, client: TestClient) -> None:
        response = client.get("/invoices/sync", headers={"X-Tenant-ID": "acme"})
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 2
        assert all(r["tenant_id"] == "acme" for r in rows)

    def test_sync_route_returns_only_globex_invoices(self, client: TestClient) -> None:
        response = client.get("/invoices/sync", headers={"X-Tenant-ID": "globex"})
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 1
        assert all(r["tenant_id"] == "globex" for r in rows)

    def test_async_route_returns_filtered_results(self, client: TestClient) -> None:
        """Async + threadpool pattern preserves tenant scope (Rule 55)."""
        response = client.get("/invoices/async", headers={"X-Tenant-ID": "acme"})
        assert response.status_code == 200
        rows = response.json()
        assert all(r["tenant_id"] == "acme" for r in rows)

    def test_no_header_default_mode_falls_through(self, client: TestClient) -> None:
        """Default ``allow_unrestricted`` mode: no header → no filtering (DR-022)."""
        response = client.get("/invoices/sync")
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 3  # 2 acme + 1 globex


class TestFastAPIStrictMode:
    """Verify ``on_missing_tenant='raise'`` strict mode (DR-026)."""

    def test_strict_mode_with_tenant_proceeds(self, strict_client: TestClient) -> None:
        response = strict_client.get("/invoices", headers={"X-Tenant-ID": "acme"})
        assert response.status_code == 200

    def test_strict_mode_without_tenant_raises(self, strict_client: TestClient) -> None:
        """Strict mode + no header → MissingTenantContextError propagates."""
        with pytest.raises(MissingTenantContextError):
            strict_client.get("/invoices")
