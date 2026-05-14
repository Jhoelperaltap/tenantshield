"""Django adapter for TenantShield -- ORM enforcement core."""

from __future__ import annotations

from tenantshield.adapters.django.decorators import tenant_aware
from tenantshield.adapters.django.managers import (
    TenantAwareManager,
    TenantAwareQuerySet,
)

__all__ = [
    "TenantAwareManager",
    "TenantAwareQuerySet",
    "tenant_aware",
]
