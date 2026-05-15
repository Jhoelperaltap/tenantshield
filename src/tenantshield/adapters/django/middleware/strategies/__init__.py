"""Tenant extraction strategies for Django middleware.

This subpackage hosts the TenantExtractionStrategy Protocol (see base.py)
and its four built-in implementations (Subdomain, Header, JWT, Callable),
plus a resolve_strategy() function for translating Django settings into
strategy instances.

In Sub-phase 2B.4, all four implementations are materialized and the
resolve_strategy() dispatch function is added. Middleware integration
arrives in 2B.5.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.core.exceptions import ImproperlyConfigured

from tenantshield.adapters.django.middleware.strategies.base import (
    TenantExtractionStrategy,
)
from tenantshield.adapters.django.middleware.strategies.callable_ import (
    CallableStrategy,
)
from tenantshield.adapters.django.middleware.strategies.header import (
    HeaderStrategy,
)
from tenantshield.adapters.django.middleware.strategies.jwt import (
    JWTStrategy,
)
from tenantshield.adapters.django.middleware.strategies.subdomain import (
    SubdomainStrategy,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from django.http import HttpRequest


def resolve_strategy(config: Mapping[str, object]) -> TenantExtractionStrategy:
    """Construct a strategy from configuration dict.

    Examples of config:
        {"tenant_extraction": "subdomain"}
        {"tenant_extraction": "header", "header_name": "X-Tenant-Id"}
        {"tenant_extraction": "jwt", "jwt_secret": "...", "jwt_claim": "tenant_id"}
        {"tenant_extraction": callable_fn}

    Args:
        config: Mapping (typically ``settings.TENANTSHIELD``) carrying
            the ``tenant_extraction`` key plus strategy-specific
            options.

    Returns:
        Instance of a class conforming to TenantExtractionStrategy.

    Raises:
        ImproperlyConfigured: when ``tenant_extraction`` is missing or
            holds an unknown string value.
    """
    extraction = config.get("tenant_extraction")
    if extraction is None:
        msg = (
            "TENANTSHIELD['tenant_extraction'] is not configured. "
            "Set it to 'subdomain', 'header', 'jwt', or a callable."
        )
        raise ImproperlyConfigured(msg)

    if extraction == "subdomain":
        return SubdomainStrategy()
    if extraction == "header":
        return HeaderStrategy(
            header_name=str(config.get("header_name", "X-Tenant-Id")),
        )
    if extraction == "jwt":
        return JWTStrategy(
            secret=str(config["jwt_secret"]),
            claim=str(config.get("jwt_claim", "tenant_id")),
            algorithm=str(config.get("jwt_algorithm", "HS256")),
        )
    if callable(extraction):
        # The user-supplied callable must conform to the Callable[[HttpRequest], str]
        # contract documented for CallableStrategy; we cast to the narrowed type
        # so the CallableStrategy constructor signature is satisfied.
        return CallableStrategy(cast("Callable[[HttpRequest], str]", extraction))

    msg = f"Unknown tenant_extraction value: {extraction!r}"
    raise ImproperlyConfigured(msg)


__all__ = [
    "CallableStrategy",
    "HeaderStrategy",
    "JWTStrategy",
    "SubdomainStrategy",
    "TenantExtractionStrategy",
    "resolve_strategy",
]
