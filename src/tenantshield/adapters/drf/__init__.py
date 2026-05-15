"""TenantShield DRF adapter.

This package hosts the Django REST Framework integration:
- IsSameTenant permission (request-level + object-level enforcement).
- TenantAwareViewSetMixin (ViewSet pre-filtering).
- TenantValidatedSerializerMixin (write-path tenant validation).

All three are materialized in Sub-phase 2C tasks 2C.A.1 through 2C.A.3.
DR-019 documents the triple-defense architecture as three independent
layers in distinct points of the DRF request lifecycle.
"""

from __future__ import annotations

from tenantshield.adapters.drf.exceptions import TenantPermissionDenied
from tenantshield.adapters.drf.mixins import TenantAwareViewSetMixin
from tenantshield.adapters.drf.permissions import IsSameTenant
from tenantshield.adapters.drf.serializers import TenantValidatedSerializerMixin

__all__ = [
    "IsSameTenant",
    "TenantAwareViewSetMixin",
    "TenantPermissionDenied",
    "TenantValidatedSerializerMixin",
]
