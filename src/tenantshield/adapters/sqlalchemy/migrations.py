"""Migration metadata helpers for SA ``@tenant_aware`` mapped classes.

SA parity surface for the Django ``adapters.django.migrations``
module shipped in Phase 6 D-MIG.0. Per D-AUDIT-SA-PARITY (2026-05-23)
Category 3 gap. The SA adapter previously had no way to enumerate
its registered tenant-aware classes; this module provides that
introspection surface for adopter migrations, management commands,
audit dashboards, and Alembic env helpers.

The implementation uses the module-level ``_registered_models`` set
in ``adapters.sqlalchemy.decorator``, populated at decoration time
(Option A per Phase 6.1 D-HOTFIX-v061 architectural decision). The
set is decoration-time-written and runtime-readonly in practice;
the SA decorator is invoked once per mapped class at import time,
so race conditions are not a concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tenantshield.adapters.sqlalchemy.decorator import (
    _registered_models,  # pyright: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True, slots=True, kw_only=True)
class TenantAwareModelMetadata:
    """Snapshot of an SA tenant-aware mapped class's decoration-time state.

    Attributes:
        model_qualname: ``"<module>.<Class>"`` identifier suitable for
            cross-reference in Alembic env scripts and audit dashboards.
        tenant_field: The mapped column name carrying the tenant id.
            Currently always ``"tenant_id"`` (the SA decorator hardcodes
            the column name; cf. ``adapters.sqlalchemy.decorator``).
        auto_propagate_from_parent_fk: Whether the model opted into FK
            auto-propagation. Currently always ``False`` (SA-AUTO.0 is
            Phase 7 candidate item 32; see ADR-0014 retrospective).
    """

    model_qualname: str
    tenant_field: str
    auto_propagate_from_parent_fk: bool


def tenant_aware_models() -> Iterator[TenantAwareModelMetadata]:
    """Yield metadata for every SA ``@tenant_aware`` mapped class.

    Iteration order matches the underlying ``set`` (insertion order is
    not guaranteed; callers needing deterministic order should sort by
    ``model_qualname``). The helper does not instantiate the SA
    ``DeclarativeBase`` registry; it only reads the
    ``_registered_models`` set populated at decoration time.

    Example:
        >>> from tenantshield.adapters.sqlalchemy import tenant_aware_models
        >>> for meta in sorted(tenant_aware_models(), key=lambda m: m.model_qualname):
        ...     print(meta.model_qualname, meta.tenant_field)
    """
    for model_class in _registered_models:
        yield TenantAwareModelMetadata(
            model_qualname=f"{model_class.__module__}.{model_class.__qualname__}",
            tenant_field="tenant_id",
            auto_propagate_from_parent_fk=False,
        )


def get_model_metadata(model_class: type) -> TenantAwareModelMetadata | None:
    """Return metadata for a specific SA mapped class, or ``None``.

    Useful in adopter code that needs to branch on whether a class
    is decorated with ``@tenant_aware`` (e.g., Alembic env hooks
    deciding whether to apply tenant-scoped migration policies).
    The check is O(1) (set membership lookup).
    """
    if model_class not in _registered_models:
        return None
    return TenantAwareModelMetadata(
        model_qualname=f"{model_class.__module__}.{model_class.__qualname__}",
        tenant_field="tenant_id",
        auto_propagate_from_parent_fk=False,
    )
