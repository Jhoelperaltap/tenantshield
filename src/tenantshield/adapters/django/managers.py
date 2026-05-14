"""Custom Manager and QuerySet for tenant-aware Django models.

This module is a stub in Sub-phase 2A.3. Full implementation arrives in 2A.4.
"""

from __future__ import annotations

from django.db import models


# Generic parametrization and from_queryset typing are addressed in 2A.4 when
# the QuerySet bound type and the public Manager surface are nailed down.
class TenantAwareQuerySet(models.QuerySet):  # type: ignore[type-arg]  # pyright: ignore[reportMissingTypeArgument]
    """Stub. Full implementation in 2A.4."""


class TenantAwareManager(models.Manager.from_queryset(TenantAwareQuerySet)):  # type: ignore[misc]  # pyright: ignore[reportUnknownMemberType, reportGeneralTypeIssues]
    """Stub. Full implementation in 2A.4."""

    use_in_migrations = False
