"""TenantShield DRF adapter.

This package hosts the Django REST Framework integration:
- IsSameTenant permission (request-level + object-level enforcement).
- TenantAwareViewSetMixin (ViewSet pre-filtering).
- TenantValidatedSerializerMixin (write-path tenant validation).

All three are materialized in Sub-phase 2C tasks 2C.A.1 through 2C.A.3.
DR-019 documents the triple-defense architecture.
"""

from __future__ import annotations

from tenantshield.adapters.drf.exceptions import TenantPermissionDenied
from tenantshield.adapters.drf.permissions import IsSameTenant

__all__ = [
    "IsSameTenant",
    "TenantPermissionDenied",
]
