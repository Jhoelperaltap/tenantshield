"""Cross-adapter integration tests demonstrating Phase 4B unification.

These tests verify empirically that **the same strategy class instance**
works via both Django (``DjangoRequestAdapter`` wrapping ``HttpRequest``)
and SQLAlchemy (``AsgiRequestAdapter`` wrapping ASGI scope) adapter
wrappers. Closes BLOCKER #30 (Phase 2B Django-bound strategies) deferral
empirically end-to-end.

The ``tests/integration/django/conftest.py`` configures Django via
``DJANGO_SETTINGS_MODULE``; that conftest does NOT apply to this file
(different directory). This module configures Django at import time
with permissive ``ALLOWED_HOSTS`` so ``HttpRequest.get_host()`` works
across the test scenarios.
"""

from __future__ import annotations

import django
import jwt as pyjwt
import pytest
from django.conf import settings

if not settings.configured:  # pragma: no cover -- module-level Django setup
    settings.configure(
        DEBUG=False,
        INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth"],
        ALLOWED_HOSTS=["*"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    )
    django.setup()

from django.test import (
    RequestFactory,
)

from tenantshield import resolve_strategy as top_resolve_strategy
from tenantshield.adapters.django.middleware.strategies import (
    DjangoRequestAdapter,
)
from tenantshield.adapters.sqlalchemy import AsgiRequestAdapter
from tenantshield.strategies import (
    CallableStrategy,
    HeaderStrategy,
    HostStrategy,
    JWTStrategy,
    RequestProtocol,
    TenantExtractionError,
)

_TEST_JWT_SECRET = "test-secret-32-bytes-or-longer-for-hs256-key"  # noqa: S105


@pytest.fixture
def rf() -> RequestFactory:
    """Django RequestFactory."""
    return RequestFactory()


def _asgi_scope(headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    """Build minimal ASGI HTTP scope dict."""
    return {"type": "http", "method": "GET", "path": "/", "headers": headers or []}


class TestSameStrategyAcrossAdapters:
    """Single strategy instance extracts via both DjangoRequestAdapter + AsgiRequestAdapter."""

    def test_header_strategy_extracts_via_both_adapters(self, rf: RequestFactory) -> None:
        strategy = HeaderStrategy()  # Single instance shared

        django_request = rf.get("/", HTTP_X_TENANT_ID="acme")
        django_adapter = DjangoRequestAdapter(django_request)
        django_result = strategy.extract(django_adapter)

        asgi_adapter = AsgiRequestAdapter(_asgi_scope([(b"x-tenant-id", b"acme")]))
        sa_result = strategy.extract(asgi_adapter)

        assert django_result == "acme"
        assert sa_result == "acme"
        assert django_result == sa_result

    def test_host_strategy_extracts_via_both_adapters(self, rf: RequestFactory) -> None:
        strategy = HostStrategy()  # Single instance shared

        django_request = rf.get("/", HTTP_HOST="acme.example.com")
        django_adapter = DjangoRequestAdapter(django_request)
        django_result = strategy.extract(django_adapter)

        asgi_adapter = AsgiRequestAdapter(_asgi_scope([(b"host", b"acme.example.com")]))
        sa_result = strategy.extract(asgi_adapter)

        assert django_result == "acme"
        assert sa_result == "acme"
        assert django_result == sa_result

    def test_jwt_strategy_extracts_via_both_adapters(self, rf: RequestFactory) -> None:
        token = pyjwt.encode({"tenant_id": "umbrella"}, _TEST_JWT_SECRET, algorithm="HS256")
        strategy = JWTStrategy(secret=_TEST_JWT_SECRET)  # Single instance shared

        django_request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        django_adapter = DjangoRequestAdapter(django_request)
        django_result = strategy.extract(django_adapter)

        asgi_adapter = AsgiRequestAdapter(
            _asgi_scope([(b"authorization", f"Bearer {token}".encode())]),
        )
        sa_result = strategy.extract(asgi_adapter)

        assert django_result == "umbrella"
        assert sa_result == "umbrella"
        assert django_result == sa_result

    def test_callable_strategy_extracts_via_both_adapters(self, rf: RequestFactory) -> None:
        def extractor(req: RequestProtocol) -> str:
            return req.get_header("X-Tenant-Id") or ""

        strategy = CallableStrategy(extractor)

        django_request = rf.get("/", HTTP_X_TENANT_ID="acme")
        django_adapter = DjangoRequestAdapter(django_request)
        django_result = strategy.extract(django_adapter)

        asgi_adapter = AsgiRequestAdapter(_asgi_scope([(b"x-tenant-id", b"acme")]))
        sa_result = strategy.extract(asgi_adapter)

        assert django_result == "acme"
        assert sa_result == "acme"


class TestResolveStrategyProducesCrossAdapterStrategies:
    """``resolve_strategy()`` output works via both adapter wrappers."""

    def test_resolved_header_strategy_works_cross_adapter(self, rf: RequestFactory) -> None:
        strategy = top_resolve_strategy({"tenant_extraction": "header"})

        django_request = rf.get("/", HTTP_X_TENANT_ID="acme")
        django_result = strategy.extract(DjangoRequestAdapter(django_request))

        asgi_adapter = AsgiRequestAdapter(_asgi_scope([(b"x-tenant-id", b"acme")]))
        sa_result = strategy.extract(asgi_adapter)

        assert django_result == sa_result == "acme"

    def test_resolved_host_strategy_works_cross_adapter(self, rf: RequestFactory) -> None:
        strategy = top_resolve_strategy({"tenant_extraction": "host"})

        django_request = rf.get("/", HTTP_HOST="globex.example.com")
        django_result = strategy.extract(DjangoRequestAdapter(django_request))

        asgi_adapter = AsgiRequestAdapter(_asgi_scope([(b"host", b"globex.example.com")]))
        sa_result = strategy.extract(asgi_adapter)

        assert django_result == sa_result == "globex"

    def test_resolved_jwt_strategy_works_cross_adapter(self, rf: RequestFactory) -> None:
        token = pyjwt.encode({"tenant_id": "umbrella"}, _TEST_JWT_SECRET, algorithm="HS256")
        strategy = top_resolve_strategy(
            {"tenant_extraction": "jwt", "jwt_secret": _TEST_JWT_SECRET},
        )

        django_request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        django_result = strategy.extract(DjangoRequestAdapter(django_request))

        asgi_adapter = AsgiRequestAdapter(
            _asgi_scope([(b"authorization", f"Bearer {token}".encode())]),
        )
        sa_result = strategy.extract(asgi_adapter)

        assert django_result == sa_result == "umbrella"


class TestCrossAdapterErrorParity:
    """Strategy contract failures behave identically across adapters."""

    def test_jwt_invalid_signature_raises_both_adapters(self, rf: RequestFactory) -> None:
        token = pyjwt.encode(
            {"tenant_id": "x"},
            "wrong-secret-32-bytes-or-longer-string-for-test",
            algorithm="HS256",
        )
        strategy = JWTStrategy(secret=_TEST_JWT_SECRET)

        django_request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        with pytest.raises(TenantExtractionError):
            strategy.extract(DjangoRequestAdapter(django_request))

        asgi_adapter = AsgiRequestAdapter(
            _asgi_scope([(b"authorization", f"Bearer {token}".encode())]),
        )
        with pytest.raises(TenantExtractionError):
            strategy.extract(asgi_adapter)
