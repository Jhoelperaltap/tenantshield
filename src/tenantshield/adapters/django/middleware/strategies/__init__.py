"""Tenant extraction strategies for Django middleware.

This subpackage hosts the TenantExtractionStrategy Protocol (see base.py)
and its four built-in implementations (Subdomain, Header, JWT, Callable),
plus a resolve_strategy() function for translating Django settings into
strategy instances.

In Sub-phase 2B.2, only the Protocol is materialized. Implementations
arrive in 2B.3 (Subdomain, Header) and 2B.4 (Callable, JWT).
"""

from __future__ import annotations

from tenantshield.adapters.django.middleware.strategies.base import (
    TenantExtractionStrategy,
)

__all__ = [
    "TenantExtractionStrategy",
]
