"""Migration metadata helpers for ``@tenant_aware`` models.

Per Finding #3 (Counterbook ADR-0015 catalog): the metadata that
``@tenant_aware`` attaches at decoration time (registry entry +
``_tenantshield_*`` class flags + installed managers) is runtime
state, not part of the model class body. This module exposes a
small inspection API so adopter migrations, management commands,
and audit scripts can introspect that runtime state without
reaching into private attributes.

The helpers are intentionally **read-only**; they do not modify
the model or the registry. They exist to support cosmetic uses:
generating documentation, listing tenant-aware models in admin
dashboards, sanity-checking migration plans, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tenantshield.registry import default_registry

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.db.models import Model


@dataclass(frozen=True, slots=True, kw_only=True)
class TenantAwareModelMetadata:
    """Snapshot of a tenant-aware model's decoration-time state.

    Attributes:
        model_qualname: ``"<module>.<Class>"`` identifier suitable for
            cross-reference in migrations and audit dashboards.
        tenant_field: The model attribute carrying the tenant id (set
            by ``@tenant_aware(tenant_field=...)``).
        audit_cross_tenant_attempts: Flag set by
            ``@tenant_aware(audit_cross_tenant_attempts=True)`` (D-CTA.0).
        auto_propagate_from_parent_fk: Flag set by
            ``@tenant_aware(auto_propagate_from_parent_fk=True)`` (D-AUTO.0).
    """

    model_qualname: str
    tenant_field: str
    audit_cross_tenant_attempts: bool
    auto_propagate_from_parent_fk: bool


def tenant_aware_models() -> Iterator[TenantAwareModelMetadata]:
    """Yield metadata for every registered tenant-aware model.

    Iteration order matches the registry (insertion order). The
    helper does not load Django apps; if a model is registered but
    its Django app config is not yet ready, this still yields it.

    Example:
        >>> from tenantshield.adapters.django import tenant_aware_models
        >>> for meta in tenant_aware_models():
        ...     print(meta.model_qualname, meta.tenant_field)
    """
    for entry in default_registry:
        model = entry.model
        yield TenantAwareModelMetadata(
            model_qualname=f"{model.__module__}.{model.__qualname__}",
            tenant_field=entry.tenant_field,
            audit_cross_tenant_attempts=bool(
                getattr(model, "_tenantshield_audit_cross_tenant", False)
            ),
            auto_propagate_from_parent_fk=bool(
                getattr(model, "_tenantshield_auto_propagate_from_parent_fk", False)
            ),
        )


def get_model_metadata(model: type[Model]) -> TenantAwareModelMetadata | None:
    """Return metadata for a specific model, or ``None`` if not tenant-aware.

    Useful in adopter code that needs to branch on whether a Django
    model class is decorated with ``@tenant_aware``. The check is
    O(1) (registry membership lookup).
    """
    if not default_registry.is_registered(model):
        return None
    entry = default_registry.get(model)
    return TenantAwareModelMetadata(
        model_qualname=f"{model.__module__}.{model.__qualname__}",
        tenant_field=entry.tenant_field,
        audit_cross_tenant_attempts=bool(getattr(model, "_tenantshield_audit_cross_tenant", False)),
        auto_propagate_from_parent_fk=bool(
            getattr(model, "_tenantshield_auto_propagate_from_parent_fk", False)
        ),
    )
