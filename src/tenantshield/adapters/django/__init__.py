"""Django adapter for TenantShield -- ORM enforcement + middleware."""

from __future__ import annotations

from tenantshield.adapters.django.decorators import tenant_aware
from tenantshield.adapters.django.managers import (
    TenantAwareManager,
    TenantAwareQuerySet,
    UnsafeUnscopedManager,
    UnsafeUnscopedQuerySet,
)
from tenantshield.adapters.django.middleware import TenantContextMiddleware

__all__ = [
    "TenantAwareManager",
    "TenantAwareQuerySet",
    "TenantContextMiddleware",
    "UnsafeUnscopedManager",
    "UnsafeUnscopedQuerySet",
    "tenant_aware",
]
