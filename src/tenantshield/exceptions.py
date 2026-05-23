"""Exception hierarchy for TenantShield.

All errors raised by TenantShield are subclasses of :class:`TenantShieldError`.
The hierarchy is::

    TenantShieldError
    ├── ConfigurationError
    ├── TenantContextError
    │   ├── MissingTenantContextError
    │   └── AmbiguousTenantContextError
    ├── EnforcementError
    │   ├── CrossTenantAccessError
    │   ├── UnscopedQueryError
    │   └── CrossTenantJoinError
    └── AdapterError

Errors with structured fields carry contextual information (tenant ids, model
names, operation labels). They expose a :meth:`to_dict` method for serialization
to audit sinks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tenantshield._types import TenantId


def _empty_metadata() -> dict[str, object]:
    """Factory for the default empty metadata mapping of dataclass-based errors."""
    return {}


class TenantShieldError(Exception):
    """Base class for all TenantShield errors."""


class ConfigurationError(TenantShieldError):
    """Raised when TenantShield is misconfigured or used in an unsupported way."""


class TenantContextError(TenantShieldError):
    """Base class for tenant context problems."""


class EnforcementError(TenantShieldError):
    """Base class for tenant isolation policy violations."""


class AdapterError(TenantShieldError):
    """Base class for adapter-specific failures."""


_MISSING_TENANT_CONTEXT_HINT = (
    "Canonical pattern: `with tenant_scope(bind_tenant(TenantId(str(company.id)))):` "
    "or Django shortcut: `with tenant_scope_for_company(company):` "
    "(from `tenantshield.adapters.django`)."
)


@dataclass
class MissingTenantContextError(TenantContextError):
    """Raised when an operation requires a tenant scope and none is active.

    The auto-generated message includes a canonical-pattern hint pointing
    callers at the documented entry-point shapes (raw API + Django
    shortcut) per Finding #2 (Counterbook ADR-0015 catalog).

    Args:
        operation: A short label identifying the API or operation that needed
            the tenant context (e.g. ``"current_tenant"``, ``"query.all"``).
        stack_context: Optional dictionary with additional debugging context.
    """

    operation: str
    stack_context: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        msg = (
            f"Missing tenant context for operation {self.operation!r}. "
            f"{_MISSING_TENANT_CONTEXT_HINT}"
        )
        super().__init__(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "type": type(self).__name__,
            "operation": self.operation,
            "stack_context": dict(self.stack_context),
        }


@dataclass
class AmbiguousTenantContextError(TenantContextError):
    """Raised when nested tenant scopes carry conflicting tenant identifiers.

    Args:
        tenant_id_outer: Tenant active in the surrounding scope.
        tenant_id_inner: Tenant the inner scope attempted to activate.
        stack_context: Optional dictionary with additional debugging context.
    """

    tenant_id_outer: TenantId
    tenant_id_inner: TenantId
    stack_context: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        msg = (
            f"Ambiguous tenant context: outer={self.tenant_id_outer!r} "
            f"inner={self.tenant_id_inner!r} — nested scopes with conflicting tenants."
        )
        super().__init__(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "type": type(self).__name__,
            "tenant_id_outer": self.tenant_id_outer,
            "tenant_id_inner": self.tenant_id_inner,
            "stack_context": dict(self.stack_context),
        }


@dataclass
class CrossTenantAccessError(EnforcementError):
    """Raised when an access crosses tenant boundaries.

    Args:
        tenant_id_expected: The tenant that should have scoped the access.
        tenant_id_actual: The tenant actually carried by the data.
        model: Name of the model or table involved.
        operation: Short label identifying the operation (e.g. ``"read"``).
        stack_context: Optional dictionary with additional debugging context.
    """

    tenant_id_expected: TenantId | None
    tenant_id_actual: TenantId | None
    model: str | None
    operation: str
    stack_context: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        msg = (
            f"Cross-tenant access detected: expected tenant {self.tenant_id_expected!r}, "
            f"got {self.tenant_id_actual!r} on model {self.model!r} during {self.operation!r}."
        )
        super().__init__(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "type": type(self).__name__,
            "tenant_id_expected": self.tenant_id_expected,
            "tenant_id_actual": self.tenant_id_actual,
            "model": self.model,
            "operation": self.operation,
            "stack_context": dict(self.stack_context),
        }


@dataclass
class UnscopedQueryError(EnforcementError):
    """Raised when a query touches a tenant-aware model without an active scope.

    Args:
        model: Name of the tenant-aware model that was queried.
        operation: Short label identifying the operation (e.g. ``"filter"``).
        stack_context: Optional dictionary with additional debugging context.
    """

    model: str | None
    operation: str
    stack_context: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        msg = (
            f"Unscoped query on tenant-aware model {self.model!r} during "
            f"{self.operation!r} — no tenant scope active."
        )
        super().__init__(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "type": type(self).__name__,
            "model": self.model,
            "operation": self.operation,
            "stack_context": dict(self.stack_context),
        }


@dataclass
class CrossTenantJoinError(EnforcementError):
    """Raised when a query joins models that belong to different tenants.

    Args:
        tenant_id_expected: The tenant under which the join was attempted.
        model_left: Name of the left side of the join.
        model_right: Name of the right side of the join.
        stack_context: Optional dictionary with additional debugging context.
    """

    tenant_id_expected: TenantId | None
    model_left: str
    model_right: str
    stack_context: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        msg = (
            f"Cross-tenant join detected between {self.model_left!r} and "
            f"{self.model_right!r} under tenant {self.tenant_id_expected!r}."
        )
        super().__init__(msg)

    def to_dict(self) -> dict[str, object]:
        return {
            "type": type(self).__name__,
            "tenant_id_expected": self.tenant_id_expected,
            "model_left": self.model_left,
            "model_right": self.model_right,
            "stack_context": dict(self.stack_context),
        }


__all__ = [
    "AdapterError",
    "AmbiguousTenantContextError",
    "ConfigurationError",
    "CrossTenantAccessError",
    "CrossTenantJoinError",
    "EnforcementError",
    "MissingTenantContextError",
    "TenantContextError",
    "TenantShieldError",
    "UnscopedQueryError",
]
