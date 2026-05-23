"""Django adapter for TenantShield -- ORM enforcement + middleware."""

from __future__ import annotations

from tenantshield.adapters.django.admin import TenantAwareAdmin
from tenantshield.adapters.django.decorators import tenant_aware
from tenantshield.adapters.django.managers import (
    TenantAwareManager,
    TenantAwareQuerySet,
    UnsafeUnscopedManager,
    UnsafeUnscopedQuerySet,
)
from tenantshield.adapters.django.middleware import TenantContextMiddleware
from tenantshield.adapters.django.migrations import (
    TenantAwareModelMetadata,
    get_model_metadata,
    tenant_aware_models,
)
from tenantshield.adapters.django.scope import tenant_scope_for_company

__all__ = [
    "TenantAwareAdmin",
    "TenantAwareManager",
    "TenantAwareModelMetadata",
    "TenantAwareQuerySet",
    "TenantContextMiddleware",
    "UnsafeUnscopedManager",
    "UnsafeUnscopedQuerySet",
    "get_model_metadata",
    "tenant_aware",
    "tenant_aware_models",
    "tenant_scope_for_company",
]
