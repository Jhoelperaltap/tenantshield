"""Tests for DjangoRequestAdapter -- HttpRequest -> RequestProtocol bridge.

Verifies the Sub-fase 4B Tarea 4B.2 adapter wrapper conforms to
``tenantshield.strategies.RequestProtocol`` and exposes Django HttpRequest
data via the framework-agnostic surface.
"""

from __future__ import annotations

import pytest
from django.test import RequestFactory

from tenantshield.adapters.django.middleware.strategies import DjangoRequestAdapter
from tenantshield.strategies import RequestProtocol


@pytest.fixture
def rf() -> RequestFactory:
    """Django RequestFactory fixture."""
    return RequestFactory()


class TestDjangoRequestAdapter:
    """Verify DjangoRequestAdapter bridges HttpRequest to RequestProtocol."""

    def test_get_header_returns_value_when_present(self, rf):
        request = rf.get("/", HTTP_X_TENANT_ID="acme")
        adapter = DjangoRequestAdapter(request)
        assert adapter.get_header("X-Tenant-Id") == "acme"

    def test_get_header_case_insensitive(self, rf):
        request = rf.get("/", HTTP_X_TENANT_ID="acme")
        adapter = DjangoRequestAdapter(request)
        # Django headers attribute provides case-insensitive lookup
        assert adapter.get_header("x-tenant-id") == "acme"

    def test_get_header_returns_none_when_missing(self, rf):
        request = rf.get("/")
        adapter = DjangoRequestAdapter(request)
        assert adapter.get_header("X-Missing-Header") is None

    def test_get_host_returns_request_host(self, rf):
        request = rf.get("/", HTTP_HOST="acme.example.com")
        adapter = DjangoRequestAdapter(request)
        assert adapter.get_host() == "acme.example.com"

    def test_get_host_includes_port(self, rf):
        request = rf.get("/", HTTP_HOST="globex.example.com:8000")
        adapter = DjangoRequestAdapter(request)
        assert adapter.get_host() == "globex.example.com:8000"

    def test_conforms_to_request_protocol(self, rf):
        request = rf.get("/")
        adapter = DjangoRequestAdapter(request)
        assert isinstance(adapter, RequestProtocol)
