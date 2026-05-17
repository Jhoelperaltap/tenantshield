"""Unit tests for tenant extraction strategies."""

from __future__ import annotations

from unittest.mock import patch

import jwt as pyjwt
import pytest
from django.core.exceptions import ImproperlyConfigured

from tenantshield.adapters.django.exceptions import TenantExtractionError
from tenantshield.adapters.django.middleware.strategies import (
    CallableStrategy,
    HeaderStrategy,
    JWTStrategy,
    SubdomainStrategy,
    TenantExtractionStrategy,
    resolve_strategy,
)

# Use 32+ bytes for HS256 to avoid PyJWT warning noise (per 2B.4 closure note).
_TEST_JWT_SECRET = "test-secret-32-bytes-or-longer-for-hs256-key"  # noqa: S105 -- test fixture, not a real secret


@pytest.fixture
def rf():
    """RequestFactory fixture for synthetic requests."""
    from django.test import RequestFactory  # noqa: PLC0415

    return RequestFactory()


# === SubdomainStrategy ===


class TestSubdomainStrategy:
    """Tests for SubdomainStrategy."""

    def test_extracts_subdomain_from_three_part_host(self, rf):
        request = rf.get("/", HTTP_HOST="acme.example.com")
        assert SubdomainStrategy().extract(request) == "acme"

    def test_strips_port_from_host(self, rf):
        request = rf.get("/", HTTP_HOST="globex.example.com:8000")
        assert SubdomainStrategy().extract(request) == "globex"

    def test_handles_deeper_subdomains(self, rf):
        # Four-part host: 'team.acme.example.com' -> 'team'.
        request = rf.get("/", HTTP_HOST="team.acme.example.com")
        assert SubdomainStrategy().extract(request) == "team"

    def test_raises_on_two_part_host(self, rf):
        request = rf.get("/", HTTP_HOST="example.com")
        with pytest.raises(TenantExtractionError) as exc_info:
            SubdomainStrategy().extract(request)
        assert "example.com" in exc_info.value.reason
        assert exc_info.value.strategy_name == "SubdomainStrategy"

    def test_raises_on_localhost(self, rf):
        request = rf.get("/", HTTP_HOST="localhost")
        with pytest.raises(TenantExtractionError):
            SubdomainStrategy().extract(request)

    def test_conforms_to_protocol(self):
        assert isinstance(SubdomainStrategy(), TenantExtractionStrategy)


# === HeaderStrategy ===


class TestHeaderStrategy:
    """Tests for HeaderStrategy."""

    def test_extracts_default_header(self, rf):
        request = rf.get("/", HTTP_X_TENANT_ID="initech")
        assert HeaderStrategy().extract(request) == "initech"

    def test_extracts_custom_header(self, rf):
        request = rf.get("/", HTTP_X_COMPANY="umbrella")
        assert HeaderStrategy(header_name="X-Company").extract(request) == "umbrella"

    def test_raises_when_header_missing(self, rf):
        request = rf.get("/")
        with pytest.raises(TenantExtractionError) as exc_info:
            HeaderStrategy().extract(request)
        assert exc_info.value.strategy_name == "HeaderStrategy"
        assert "X-Tenant-Id" in exc_info.value.reason

    def test_raises_when_header_empty(self, rf):
        request = rf.get("/", HTTP_X_TENANT_ID="")
        with pytest.raises(TenantExtractionError):
            HeaderStrategy().extract(request)

    def test_header_name_case_insensitive_in_meta(self, rf):
        # Django META keys are uppercase by convention. Strategy normalizes.
        request = rf.get("/", HTTP_X_TENANT_ID="acme")
        # Both 'X-Tenant-Id' and 'x-tenant-id' produce the same meta key.
        assert HeaderStrategy(header_name="x-tenant-id").extract(request) == "acme"

    def test_conforms_to_protocol(self):
        assert isinstance(HeaderStrategy(), TenantExtractionStrategy)


# === CallableStrategy ===


class TestCallableStrategy:
    """Tests for CallableStrategy."""

    def test_invokes_callable_and_returns_result(self, rf):
        def extractor(_request):
            return "initech"

        request = rf.get("/")
        assert CallableStrategy(extractor).extract(request) == "initech"

    def test_extracts_from_query_param(self, rf):
        def extractor(request):
            return request.GET.get("tenant", "")

        request = rf.get("/?tenant=foo")
        assert CallableStrategy(extractor).extract(request) == "foo"

    def test_raises_when_callable_returns_none(self, rf):
        request = rf.get("/")
        with pytest.raises(TenantExtractionError) as exc_info:
            CallableStrategy(lambda _: None).extract(request)
        assert exc_info.value.strategy_name == "CallableStrategy"

    def test_raises_when_callable_returns_empty_string(self, rf):
        request = rf.get("/")
        with pytest.raises(TenantExtractionError):
            CallableStrategy(lambda _: "").extract(request)

    def test_conforms_to_protocol(self):
        assert isinstance(CallableStrategy(lambda _: "x"), TenantExtractionStrategy)


# === JWTStrategy ===


class TestJWTStrategy:
    """Tests for JWTStrategy."""

    def test_extracts_tenant_id_from_default_claim(self, rf):
        token = pyjwt.encode(
            {"tenant_id": "umbrella"},
            _TEST_JWT_SECRET,
            algorithm="HS256",
        )
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        strategy = JWTStrategy(secret=_TEST_JWT_SECRET)
        assert strategy.extract(request) == "umbrella"

    def test_extracts_custom_claim(self, rf):
        token = pyjwt.encode(
            {"org_id": "acme"},
            _TEST_JWT_SECRET,
            algorithm="HS256",
        )
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        strategy = JWTStrategy(secret=_TEST_JWT_SECRET, claim="org_id")
        assert strategy.extract(request) == "acme"

    def test_coerces_non_string_claim_to_str(self, rf):
        # Integer claim becomes str via TenantId(str(tenant)).
        token = pyjwt.encode(
            {"tenant_id": 42},
            _TEST_JWT_SECRET,
            algorithm="HS256",
        )
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        strategy = JWTStrategy(secret=_TEST_JWT_SECRET)
        assert strategy.extract(request) == "42"

    def test_raises_when_authorization_missing(self, rf):
        request = rf.get("/")
        strategy = JWTStrategy(secret=_TEST_JWT_SECRET)
        with pytest.raises(TenantExtractionError) as exc_info:
            strategy.extract(request)
        assert "Authorization" in exc_info.value.reason

    def test_raises_when_authorization_not_bearer(self, rf):
        request = rf.get("/", HTTP_AUTHORIZATION="Basic abc123")
        strategy = JWTStrategy(secret=_TEST_JWT_SECRET)
        with pytest.raises(TenantExtractionError):
            strategy.extract(request)

    def test_raises_on_invalid_signature(self, rf):
        token = pyjwt.encode(
            {"tenant_id": "x"},
            "wrong-secret-32-bytes-or-longer-string-for-test",
            algorithm="HS256",
        )
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        strategy = JWTStrategy(secret=_TEST_JWT_SECRET)
        with pytest.raises(TenantExtractionError) as exc_info:
            strategy.extract(request)
        assert "decode failed" in exc_info.value.reason.lower()

    def test_raises_when_claim_missing(self, rf):
        token = pyjwt.encode(
            {"other_claim": "value"},
            _TEST_JWT_SECRET,
            algorithm="HS256",
        )
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        strategy = JWTStrategy(secret=_TEST_JWT_SECRET)
        with pytest.raises(TenantExtractionError) as exc_info:
            strategy.extract(request)
        assert "tenant_id" in exc_info.value.reason

    def test_init_raises_importerror_when_pyjwt_not_installed(self):
        # Simulate PyJWT not installed by patching sys.modules.
        with patch.dict("sys.modules", {"jwt": None}), pytest.raises(ImportError) as exc_info:
            JWTStrategy(secret=_TEST_JWT_SECRET)
        assert "pyjwt" in str(exc_info.value).lower()

    def test_conforms_to_protocol(self):
        assert isinstance(JWTStrategy(secret=_TEST_JWT_SECRET), TenantExtractionStrategy)


# === resolve_strategy ===


class TestResolveStrategy:
    """Tests for resolve_strategy() factory function."""

    def test_resolves_subdomain(self):
        strategy = resolve_strategy({"tenant_extraction": "subdomain"})
        assert isinstance(strategy, SubdomainStrategy)

    def test_resolves_header_with_default_name(self):
        strategy = resolve_strategy({"tenant_extraction": "header"})
        assert isinstance(strategy, HeaderStrategy)
        assert strategy.header_name == "X-Tenant-Id"

    def test_resolves_header_with_custom_name(self):
        strategy = resolve_strategy(
            {
                "tenant_extraction": "header",
                "header_name": "X-Org-Id",
            },
        )
        assert isinstance(strategy, HeaderStrategy)
        assert strategy.header_name == "X-Org-Id"

    def test_resolves_jwt_with_required_secret(self):
        strategy = resolve_strategy(
            {
                "tenant_extraction": "jwt",
                "jwt_secret": _TEST_JWT_SECRET,
            },
        )
        assert isinstance(strategy, JWTStrategy)
        assert strategy.claim == "tenant_id"  # default
        assert strategy.algorithm == "HS256"  # default

    def test_resolves_jwt_with_custom_claim_and_algorithm(self):
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

    def test_resolves_callable(self):
        def my_fn(_request):
            return "x"

        strategy = resolve_strategy({"tenant_extraction": my_fn})
        assert isinstance(strategy, CallableStrategy)

    def test_raises_when_tenant_extraction_missing(self):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            resolve_strategy({})
        assert "tenant_extraction" in str(exc_info.value)

    def test_raises_when_jwt_secret_missing(self):
        # Per DPRJ-2 resolution (Tarea 0.0 housekeeping): missing
        # `jwt_secret` raises Django-idiomatic ImproperlyConfigured
        # instead of bare KeyError. Aligns with all other config
        # validation paths in resolve_strategy.
        with pytest.raises(ImproperlyConfigured) as exc_info:
            resolve_strategy({"tenant_extraction": "jwt"})
        assert "jwt_secret" in str(exc_info.value)

    def test_raises_on_unknown_string_value(self):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            resolve_strategy({"tenant_extraction": "unknown_strategy"})
        assert "Unknown" in str(exc_info.value)
