"""End-to-end tests for Flask + TenantShield example.

Validates Sub-fase 3B WSGI middleware against a real Flask app
(Decision 8-A from Phase 3B kickoff: mock-based tests in 3B are
validated against real frameworks in 3C examples).

Empirical finding (3C.1 smoke): Flask test client propagates
``MissingTenantContextError`` directly (does NOT catch + return 500).
Tests use ``pytest.raises`` symmetrically with FastAPI example pattern.
"""

from __future__ import annotations

import pytest

from app import app as default_app
from app import strict_app
from tenantshield.exceptions import MissingTenantContextError


@pytest.fixture
def client():
    return default_app.test_client()


@pytest.fixture
def strict_client():
    return strict_app.test_client()


class TestFlaskIntegration:
    """Verify WSGI middleware + SA enforcement integration."""

    def test_request_with_acme_header_returns_only_acme(self, client) -> None:
        response = client.get("/invoices", headers={"X-Tenant-ID": "acme"})
        assert response.status_code == 200
        rows = response.json
        assert len(rows) == 2
        assert all(r["tenant_id"] == "acme" for r in rows)

    def test_request_with_globex_header_returns_only_globex(self, client) -> None:
        response = client.get("/invoices", headers={"X-Tenant-ID": "globex"})
        assert response.status_code == 200
        rows = response.json
        assert len(rows) == 1
        assert all(r["tenant_id"] == "globex" for r in rows)

    def test_no_header_default_mode_falls_through(self, client) -> None:
        """Default ``allow_unrestricted`` mode: no header -> no filtering (DR-022)."""
        response = client.get("/invoices")
        assert response.status_code == 200
        rows = response.json
        assert len(rows) == 3  # 2 acme + 1 globex


class TestFlaskStrictMode:
    """Verify ``on_missing_tenant='raise'`` strict mode (DR-026)."""

    def test_strict_mode_with_tenant_proceeds(self, strict_client) -> None:
        response = strict_client.get(
            "/invoices", headers={"X-Tenant-ID": "acme"}
        )
        assert response.status_code == 200

    def test_strict_mode_without_tenant_raises(self, strict_client) -> None:
        """Strict mode + no header -> ``MissingTenantContextError`` propagates.

        Flask test client surfaces the exception directly (verified
        empirically in Tarea 3C.1 smoke).
        """
        with pytest.raises(MissingTenantContextError):
            strict_client.get("/invoices")
