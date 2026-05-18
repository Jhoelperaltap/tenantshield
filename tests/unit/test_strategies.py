"""Unit tests for ``tenantshield.strategies`` cross-adapter foundation.

Tests the new top-level ``tenantshield.strategies`` module materialized in
Sub-fase 4B Tarea 4B.1 per Decision 4-A. Coverage:

- ``RequestProtocol`` runtime conformance (``isinstance`` check).
- Each of 4 strategies' extract semantics: success, fall-through (return
  None), and irrecoverable failure (raise ``TenantExtractionError``).
- Cross-strategy Protocol conformance.

Tests use a minimal in-test ``_FakeRequest`` stub conforming to
``RequestProtocol``. Framework-specific adapter wrappers (Django,
ASGI) are tested in their respective adapter test suites; this module
verifies the framework-agnostic strategy layer.
"""

from __future__ import annotations

import jwt as pyjwt
import pytest

import tenantshield as _ts
from tenantshield.strategies import (
    CallableStrategy,
    HeaderStrategy,
    HostStrategy,
    JWTStrategy,
    RequestProtocol,
    TenantExtractionError,
    TenantExtractionStrategy,
    resolve_strategy,
)

_TEST_JWT_SECRET = "test-secret-32-bytes-or-longer-for-hs256-key"  # noqa: S105 -- test fixture


class _FakeRequest:
    """Minimal ``RequestProtocol``-conforming stub for unit tests."""

    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        host: str = "",
    ) -> None:
        self._headers = {k.lower(): v for k, v in (headers or {}).items()}
        self._host = host

    def get_header(self, name: str) -> str | None:
        return self._headers.get(name.lower())

    def get_host(self) -> str:
        return self._host


class TestRequestProtocolConformance:
    """Verify ``_FakeRequest`` conforms to ``RequestProtocol`` runtime-check."""

    def test_fake_request_conforms(self) -> None:
        request = _FakeRequest()
        assert isinstance(request, RequestProtocol)


class TestHeaderStrategy:
    """HeaderStrategy extraction semantics."""

    def test_extracts_tenant_from_default_header(self) -> None:
        request = _FakeRequest(headers={"X-Tenant-Id": "acme"})
        assert HeaderStrategy().extract(request) == "acme"

    def test_returns_none_when_header_missing(self) -> None:
        request = _FakeRequest(headers={})
        assert HeaderStrategy().extract(request) is None

    def test_returns_none_when_header_empty(self) -> None:
        request = _FakeRequest(headers={"X-Tenant-Id": ""})
        assert HeaderStrategy().extract(request) is None

    def test_custom_header_name(self) -> None:
        request = _FakeRequest(headers={"X-Account": "globex"})
        assert HeaderStrategy(header_name="X-Account").extract(request) == "globex"

    def test_case_insensitive_lookup(self) -> None:
        request = _FakeRequest(headers={"x-tenant-id": "acme"})
        assert HeaderStrategy().extract(request) == "acme"


class TestHostStrategy:
    """HostStrategy extraction semantics."""

    def test_extracts_leftmost_subdomain(self) -> None:
        request = _FakeRequest(host="acme.example.com")
        assert HostStrategy().extract(request) == "acme"

    def test_strips_port(self) -> None:
        request = _FakeRequest(host="globex.example.com:8000")
        assert HostStrategy().extract(request) == "globex"

    def test_handles_deeper_subdomains(self) -> None:
        request = _FakeRequest(host="team.acme.example.com")
        assert HostStrategy().extract(request) == "team"

    def test_returns_none_when_two_part_host(self) -> None:
        request = _FakeRequest(host="example.com")
        assert HostStrategy().extract(request) is None

    def test_returns_none_when_localhost(self) -> None:
        request = _FakeRequest(host="localhost")
        assert HostStrategy().extract(request) is None

    def test_returns_none_when_empty_host(self) -> None:
        request = _FakeRequest(host="")
        assert HostStrategy().extract(request) is None


class TestJWTStrategy:
    """JWTStrategy extraction semantics."""

    def test_extracts_from_default_claim(self) -> None:
        token = pyjwt.encode({"tenant_id": "umbrella"}, _TEST_JWT_SECRET, algorithm="HS256")
        request = _FakeRequest(headers={"Authorization": f"Bearer {token}"})
        assert JWTStrategy(secret=_TEST_JWT_SECRET).extract(request) == "umbrella"

    def test_extracts_custom_claim(self) -> None:
        token = pyjwt.encode({"org_id": "acme"}, _TEST_JWT_SECRET, algorithm="HS256")
        request = _FakeRequest(headers={"Authorization": f"Bearer {token}"})
        strategy = JWTStrategy(secret=_TEST_JWT_SECRET, claim="org_id")
        assert strategy.extract(request) == "acme"

    def test_returns_none_when_authorization_missing(self) -> None:
        request = _FakeRequest(headers={})
        assert JWTStrategy(secret=_TEST_JWT_SECRET).extract(request) is None

    def test_returns_none_when_authorization_not_bearer(self) -> None:
        request = _FakeRequest(headers={"Authorization": "Basic abc123"})
        assert JWTStrategy(secret=_TEST_JWT_SECRET).extract(request) is None

    def test_raises_on_invalid_signature(self) -> None:
        token = pyjwt.encode(
            {"tenant_id": "x"},
            "wrong-secret-32-bytes-or-longer-string-for-test",
            algorithm="HS256",
        )
        request = _FakeRequest(headers={"Authorization": f"Bearer {token}"})
        with pytest.raises(TenantExtractionError) as exc_info:
            JWTStrategy(secret=_TEST_JWT_SECRET).extract(request)
        assert "decode failed" in exc_info.value.reason.lower()

    def test_raises_when_claim_missing(self) -> None:
        token = pyjwt.encode({"other": "value"}, _TEST_JWT_SECRET, algorithm="HS256")
        request = _FakeRequest(headers={"Authorization": f"Bearer {token}"})
        with pytest.raises(TenantExtractionError) as exc_info:
            JWTStrategy(secret=_TEST_JWT_SECRET).extract(request)
        assert "tenant_id" in exc_info.value.reason

    def test_init_raises_importerror_when_pyjwt_not_installed(self) -> None:
        """Simulates PyJWT not installed; verifies actionable ImportError."""
        from unittest.mock import patch  # noqa: PLC0415 -- patch only needed here

        with patch.dict("sys.modules", {"jwt": None}), pytest.raises(ImportError) as exc_info:
            JWTStrategy(secret=_TEST_JWT_SECRET)
        assert "pyjwt" in str(exc_info.value).lower()


class TestCallableStrategy:
    """CallableStrategy extraction semantics."""

    def test_invokes_callable_and_returns_tenant(self) -> None:
        request = _FakeRequest()

        def extractor(_req: RequestProtocol) -> str:
            return "initech"

        assert CallableStrategy(extractor).extract(request) == "initech"

    def test_returns_none_when_callable_returns_empty(self) -> None:
        request = _FakeRequest()
        assert CallableStrategy(lambda _r: "").extract(request) is None

    def test_callable_receives_request_protocol(self) -> None:
        captured: list[RequestProtocol] = []

        def extractor(req: RequestProtocol) -> str:
            captured.append(req)
            return "acme"

        request = _FakeRequest(headers={"X-Tenant-Id": "acme"}, host="acme.example.com")
        assert CallableStrategy(extractor).extract(request) == "acme"
        assert len(captured) == 1
        assert isinstance(captured[0], RequestProtocol)


class TestStrategyProtocolConformance:
    """All concrete strategies conform to ``TenantExtractionStrategy`` runtime-check."""

    def test_header_strategy_conforms(self) -> None:
        assert isinstance(HeaderStrategy(), TenantExtractionStrategy)

    def test_host_strategy_conforms(self) -> None:
        assert isinstance(HostStrategy(), TenantExtractionStrategy)

    def test_jwt_strategy_conforms(self) -> None:
        assert isinstance(JWTStrategy(secret=_TEST_JWT_SECRET), TenantExtractionStrategy)

    def test_callable_strategy_conforms(self) -> None:
        assert isinstance(CallableStrategy(lambda _r: "x"), TenantExtractionStrategy)


class TestTopLevelReExports:
    """Verify top-level ``tenantshield`` re-exports per Phase 1 core pattern."""

    def test_top_level_imports(self) -> None:
        assert _ts.HeaderStrategy is HeaderStrategy
        assert _ts.HostStrategy is HostStrategy
        assert _ts.JWTStrategy is JWTStrategy
        assert _ts.CallableStrategy is CallableStrategy
        assert _ts.RequestProtocol is RequestProtocol
        assert _ts.TenantExtractionStrategy is TenantExtractionStrategy
        assert _ts.TenantExtractionError is TenantExtractionError
        assert _ts.resolve_strategy is resolve_strategy


class TestResolveStrategy:
    """Verify ``resolve_strategy`` factory dispatches per configuration."""

    def test_resolves_header_with_default_name(self) -> None:
        strategy = resolve_strategy({"tenant_extraction": "header"})
        assert isinstance(strategy, HeaderStrategy)
        assert strategy.header_name == "X-Tenant-Id"

    def test_resolves_header_with_custom_name(self) -> None:
        strategy = resolve_strategy({"tenant_extraction": "header", "header_name": "X-Org"})
        assert isinstance(strategy, HeaderStrategy)
        assert strategy.header_name == "X-Org"

    def test_resolves_host(self) -> None:
        strategy = resolve_strategy({"tenant_extraction": "host"})
        assert isinstance(strategy, HostStrategy)

    def test_resolves_jwt_with_required_secret(self) -> None:
        strategy = resolve_strategy(
            {"tenant_extraction": "jwt", "jwt_secret": _TEST_JWT_SECRET},
        )
        assert isinstance(strategy, JWTStrategy)
        assert strategy.claim == "tenant_id"
        assert strategy.algorithm == "HS256"

    def test_resolves_jwt_with_custom_claim_and_algorithm(self) -> None:
        strategy = resolve_strategy(
            {
                "tenant_extraction": "jwt",
                "jwt_secret": _TEST_JWT_SECRET,
                "jwt_claim": "org",
                "jwt_algorithm": "HS512",
            },
        )
        assert isinstance(strategy, JWTStrategy)
        assert strategy.claim == "org"
        assert strategy.algorithm == "HS512"

    def test_resolves_callable(self) -> None:
        def my_fn(_request: RequestProtocol) -> str:
            return "x"

        strategy = resolve_strategy({"tenant_extraction": my_fn})
        assert isinstance(strategy, CallableStrategy)

    def test_raises_when_tenant_extraction_missing(self) -> None:
        with pytest.raises(ValueError, match="tenant_extraction"):
            resolve_strategy({})

    def test_raises_when_jwt_secret_missing(self) -> None:
        with pytest.raises(ValueError, match="jwt_secret"):
            resolve_strategy({"tenant_extraction": "jwt"})

    def test_raises_on_unknown_string_value(self) -> None:
        with pytest.raises(ValueError, match="Unknown tenant_extraction"):
            resolve_strategy({"tenant_extraction": "unknown_strategy"})
