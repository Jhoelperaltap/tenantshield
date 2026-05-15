"""Tenant extraction strategies for Django middleware.

This subpackage hosts the TenantExtractionStrategy Protocol (see base.py)
and its four built-in implementations (Subdomain, Header, JWT, Callable),
plus a resolve_strategy() function for translating Django settings into
strategy instances.

In Sub-phase 2B.3, Subdomain and Header strategies are materialized.
Callable and JWT arrive in 2B.4. resolve_strategy() arrives in 2B.4
when all four implementations are available.
"""

from __future__ import annotations

from tenantshield.adapters.django.middleware.strategies.base import (
    TenantExtractionStrategy,
)
from tenantshield.adapters.django.middleware.strategies.header import (
    HeaderStrategy,
)
from tenantshield.adapters.django.middleware.strategies.subdomain import (
    SubdomainStrategy,
)

__all__ = [
    "HeaderStrategy",
    "SubdomainStrategy",
    "TenantExtractionStrategy",
]
