"""Tests for AsgiRequestAdapter -- ASGI scope -> RequestProtocol bridge.

Verifies the Sub-fase 4B Tarea 4B.3 SA adapter wrapper conforms to
``tenantshield.strategies.RequestProtocol`` and exposes ASGI scope data
via the framework-agnostic surface. Also verifies cross-adapter
strategy integration: the same core ``HeaderStrategy`` /
``HostStrategy`` / ``JWTStrategy`` / ``CallableStrategy`` instances
work via ``AsgiRequestAdapter`` (paralelo Tarea 4B.2 Django integration
via ``DjangoRequestAdapter``).
"""

from __future__ import annotations

import jwt as pyjwt
import pytest

from tenantshield.adapters.sqlalchemy import (
    AsgiRequestAdapter,
    CallableStrategy,
    HeaderStrategy,
    HostStrategy,
    JWTStrategy,
    RequestProtocol,
    TenantExtractionError,
)

_TEST_JWT_SECRET = "test-secret-32-bytes-or-longer-for-hs256-key"  # noqa: S105


def _scope(headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    """Build a minimal ASGI HTTP scope dict for tests."""
    return {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
    }


class TestAsgiRequestAdapter:
    """Verify AsgiRequestAdapter bridges ASGI scope to RequestProtocol."""

    def test_get_header_returns_value_when_present(self) -> None:
        adapter = AsgiRequestAdapter(_scope([(b"x-tenant-id", b"acme")]))
        assert adapter.get_header("X-Tenant-Id") == "acme"

    def test_get_header_case_insensitive(self) -> None:
        adapter = AsgiRequestAdapter(_scope([(b"x-tenant-id", b"acme")]))
        assert adapter.get_header("x-tenant-id") == "acme"
        assert adapter.get_header("X-TENANT-ID") == "acme"

    def test_get_header_returns_none_when_missing(self) -> None:
        adapter = AsgiRequestAdapter(_scope())
        assert adapter.get_header("X-Missing") is None

    def test_get_host_from_host_header(self) -> None:
        adapter = AsgiRequestAdapter(_scope([(b"host", b"acme.example.com")]))
        assert adapter.get_host() == "acme.example.com"

    def test_get_host_returns_empty_when_missing(self) -> None:
        adapter = AsgiRequestAdapter(_scope())
        assert adapter.get_host() == ""

    def test_conforms_to_request_protocol(self) -> None:
        adapter = AsgiRequestAdapter(_scope())
        assert isinstance(adapter, RequestProtocol)


class TestStrategiesViaAsgiAdapter:
    """Cross-adapter integration: core strategies extract via AsgiRequestAdapter."""

    def test_header_strategy_extracts_via_asgi_adapter(self) -> None:
        adapter = AsgiRequestAdapter(_scope([(b"x-tenant-id", b"acme")]))
        assert HeaderStrategy().extract(adapter) == "acme"

    def test_host_strategy_extracts_via_asgi_adapter(self) -> None:
        adapter = AsgiRequestAdapter(_scope([(b"host", b"acme.example.com")]))
        assert HostStrategy().extract(adapter) == "acme"

    def test_host_strategy_returns_none_for_two_part_host(self) -> None:
        adapter = AsgiRequestAdapter(_scope([(b"host", b"example.com")]))
        assert HostStrategy().extract(adapter) is None

    def test_jwt_strategy_extracts_via_asgi_adapter(self) -> None:
        token = pyjwt.encode({"tenant_id": "umbrella"}, _TEST_JWT_SECRET, algorithm="HS256")
        adapter = AsgiRequestAdapter(_scope([(b"authorization", f"Bearer {token}".encode())]))
        assert JWTStrategy(secret=_TEST_JWT_SECRET).extract(adapter) == "umbrella"

    def test_jwt_strategy_raises_on_invalid_signature_via_asgi(self) -> None:
        token = pyjwt.encode(
            {"tenant_id": "x"},
            "wrong-secret-32-bytes-or-longer-string-for-test",
            algorithm="HS256",
        )
        adapter = AsgiRequestAdapter(_scope([(b"authorization", f"Bearer {token}".encode())]))
        with pytest.raises(TenantExtractionError):
            JWTStrategy(secret=_TEST_JWT_SECRET).extract(adapter)

    def test_callable_strategy_extracts_via_asgi_adapter(self) -> None:
        adapter = AsgiRequestAdapter(_scope([(b"x-tenant-id", b"acme")]))

        def extractor(req: RequestProtocol) -> str:
            return req.get_header("X-Tenant-Id") or ""

        assert CallableStrategy(extractor).extract(adapter) == "acme"
