"""End-to-end tests for TenantContextMiddleware via Django test Client.

These tests exercise the full request lifecycle: extract -> bind_tenant
-> tenant_scope -> view -> response. The Client uses
raise_request_exception=False so middleware raises translate to HTTP
500 (per E40 pattern).
"""

from __future__ import annotations

import pytest
from django.http import HttpResponse
from django.test import Client, override_settings

from tenantshield import TenantId, bind_tenant, tenant_scope, try_current_tenant
from tests.integration.django.testapp.models import Invoice

# === Happy paths via header strategy (default from settings) ===


class TestMiddlewareHeaderHappyPath:
    """Tests for middleware with header strategy and successful extraction."""

    @pytest.mark.django_db
    def test_extracts_and_binds_tenant_from_header(self):
        """Middleware binds tenant from header for the request lifecycle."""
        ctx_acme = bind_tenant(TenantId("acme"))
        with tenant_scope(ctx_acme):
            Invoice.objects.create(tenant_id="acme", amount=100, description="test")

        client = Client(raise_request_exception=False)
        response = client.get("/invoices/", HTTP_X_TENANT_ID="acme")
        assert response.status_code == 200
        data = response.json()
        assert data["tenant"] == "acme"
        assert data["count"] == 1

    @pytest.mark.django_db
    def test_scope_cleans_up_after_request(self):
        """tenant_scope exits cleanly after middleware processes request."""
        client = Client(raise_request_exception=False)
        client.get("/invoices/", HTTP_X_TENANT_ID="acme")
        assert try_current_tenant() is None

    @pytest.mark.django_db
    def test_filters_invoices_per_tenant(self):
        """Different tenants see different invoice counts."""
        ctx_a = bind_tenant(TenantId("acme"))
        with tenant_scope(ctx_a):
            Invoice.objects.create(tenant_id="acme", amount=100, description="a1")
            Invoice.objects.create(tenant_id="acme", amount=200, description="a2")
        ctx_g = bind_tenant(TenantId("globex"))
        with tenant_scope(ctx_g):
            Invoice.objects.create(tenant_id="globex", amount=300, description="g1")

        client = Client(raise_request_exception=False)
        resp_acme = client.get("/invoices/", HTTP_X_TENANT_ID="acme")
        assert resp_acme.json()["count"] == 2
        resp_globex = client.get("/invoices/", HTTP_X_TENANT_ID="globex")
        assert resp_globex.json()["count"] == 1


# === on_missing_tenant = "raise" (default from settings.py) ===


class TestMiddlewareOnMissingRaise:
    """Tests for middleware with default on_missing_tenant='raise'."""

    def test_returns_500_when_header_missing(self):
        """Missing header raises MissingTenantContextError, translated to 500."""
        client = Client(raise_request_exception=False)
        response = client.get("/invoices/")
        assert response.status_code == 500

    def test_returns_500_when_header_empty(self):
        """Empty header value raises, translated to 500."""
        client = Client(raise_request_exception=False)
        response = client.get("/invoices/", HTTP_X_TENANT_ID="")
        assert response.status_code == 500


# === on_missing_tenant = "404" ===


_TS_404_SETTINGS = {
    "tenant_extraction": "header",
    "header_name": "X-Tenant-Id",
    "on_missing_tenant": "404",
}


class TestMiddlewareOnMissing404:
    """Tests for middleware with on_missing_tenant='404'."""

    @override_settings(TENANTSHIELD=_TS_404_SETTINGS)
    def test_returns_404_when_header_missing(self):
        client = Client(raise_request_exception=False)
        response = client.get("/invoices/")
        assert response.status_code == 404
        assert b"Tenant not found" in response.content

    @pytest.mark.django_db
    @override_settings(TENANTSHIELD=_TS_404_SETTINGS)
    def test_proceeds_when_header_present(self):
        ctx = bind_tenant(TenantId("acme"))
        with tenant_scope(ctx):
            Invoice.objects.create(tenant_id="acme", amount=10, description="x")

        client = Client(raise_request_exception=False)
        response = client.get("/invoices/", HTTP_X_TENANT_ID="acme")
        assert response.status_code == 200


# === on_missing_tenant = "public" ===


_TS_PUBLIC_SETTINGS = {
    "tenant_extraction": "header",
    "header_name": "X-Tenant-Id",
    "on_missing_tenant": "public",
}


class TestMiddlewareOnMissingPublic:
    """Tests for middleware with on_missing_tenant='public'."""

    @pytest.mark.django_db
    @override_settings(TENANTSHIELD=_TS_PUBLIC_SETTINGS)
    def test_binds_public_tenant_when_header_missing(self):
        """Missing header binds reserved __public__ and proceeds."""
        client = Client(raise_request_exception=False)
        response = client.get("/invoices/")
        assert response.status_code == 200
        assert response.json()["tenant"] == "__public__"


# === on_missing_tenant = callable ===


def _custom_handler_response(request, exc):  # noqa: ARG001 -- handler signature is contractual
    """Test handler that returns a custom response."""
    return HttpResponse(f"handled: {exc.reason}", status=418)


def _custom_handler_passthrough(request, exc):  # noqa: ARG001 -- handler signature is contractual
    """Test handler that returns None (re-raise upstream)."""
    return


class TestMiddlewareOnMissingCallable:
    """Tests for middleware with on_missing_tenant=callable."""

    def test_callable_returning_response(self):
        """Callable returning HttpResponse short-circuits."""
        with override_settings(
            TENANTSHIELD={
                "tenant_extraction": "header",
                "on_missing_tenant": _custom_handler_response,
            },
        ):
            client = Client(raise_request_exception=False)
            response = client.get("/invoices/")
            assert response.status_code == 418
            assert b"handled:" in response.content

    def test_callable_returning_none_re_raises(self):
        """Callable returning None causes middleware to re-raise."""
        with override_settings(
            TENANTSHIELD={
                "tenant_extraction": "header",
                "on_missing_tenant": _custom_handler_passthrough,
            },
        ):
            client = Client(raise_request_exception=False)
            response = client.get("/invoices/")
            assert response.status_code == 500


# === Invalid on_missing_tenant value ===


class TestMiddlewareInvalidOnMissing:
    """Test for middleware with invalid on_missing_tenant value."""

    def test_invalid_string_raises_improperly_configured(self):
        """Invalid on_missing_tenant string raises ImproperlyConfigured at request."""
        with override_settings(
            TENANTSHIELD={
                "tenant_extraction": "header",
                "on_missing_tenant": "not_a_valid_mode",
            },
        ):
            client = Client(raise_request_exception=False)
            response = client.get("/invoices/")
            # Django converts ImproperlyConfigured to 500.
            assert response.status_code == 500


# === Cross-tenant enforcement E2E ===


class TestMiddlewareCrossTenantEnforcement:
    """End-to-end test of tenant enforcement: middleware + manager."""

    @pytest.mark.django_db
    def test_cross_tenant_invoice_returns_500(self):
        """Accessing globex invoice with acme header returns 500 (DoesNotExist)."""
        ctx = bind_tenant(TenantId("globex"))
        with tenant_scope(ctx):
            globex_invoice = Invoice.objects.create(
                tenant_id="globex",
                amount=99,
                description="cross",
            )

        client = Client(raise_request_exception=False)
        response = client.get(
            f"/invoices/{globex_invoice.pk}/",
            HTTP_X_TENANT_ID="acme",
        )
        # Manager filtering excludes globex invoice -> DoesNotExist -> 500.
        assert response.status_code == 500

    @pytest.mark.django_db
    def test_same_tenant_invoice_returns_200(self):
        """Accessing acme invoice with acme header returns 200."""
        ctx = bind_tenant(TenantId("acme"))
        with tenant_scope(ctx):
            acme_invoice = Invoice.objects.create(
                tenant_id="acme",
                amount=50,
                description="own",
            )

        client = Client(raise_request_exception=False)
        response = client.get(
            f"/invoices/{acme_invoice.pk}/",
            HTTP_X_TENANT_ID="acme",
        )
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "acme"
