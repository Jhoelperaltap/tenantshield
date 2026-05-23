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
from tenantshield.adapters.django.scope import tenant_scope_for_company

__all__ = [
    "TenantAwareManager",
    "TenantAwareQuerySet",
    "TenantContextMiddleware",
    "UnsafeUnscopedManager",
    "UnsafeUnscopedQuerySet",
    "tenant_aware",
    "tenant_scope_for_company",
]
