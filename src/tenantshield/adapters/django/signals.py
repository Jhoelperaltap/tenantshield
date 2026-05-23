"""Write-path validation via Django signals."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.db.models.signals import pre_delete, pre_save

from tenantshield._types import TenantId
from tenantshield.context import try_current_tenant
from tenantshield.exceptions import CrossTenantAccessError, MissingTenantContextError
from tenantshield.registry import default_registry

if TYPE_CHECKING:
    from collections.abc import Generator

    from django.db import models


# ADR-0013 mode 3 -- ``_unsafe_unscoped`` paths set this flag to skip
# pre_save/pre_delete validation. Uses ContextVar so async + threaded
# execution paths preserve isolation (paralelo ``TenantContext`` semantics).
_signal_bypass_var: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "tenantshield_signal_bypass",
    default=False,
)


@contextmanager
def _bypass_signal_validation() -> Generator[None, None, None]:  # pyright: ignore[reportUnusedFunction]
    """Context manager that skips ``_validate_tenant_coherence`` for the scope.

    Used by ``UnsafeUnscopedManager`` write paths (ADR-0013 mode 3) so
    that signal-driven write validation does not block legitimate
    administrative operations. Every wrapped operation MUST emit an
    ``ENFORCEMENT_BYPASS`` audit event before entering the scope.
    """
    token = _signal_bypass_var.set(True)
    try:
        yield
    finally:
        _signal_bypass_var.reset(token)


def _validate_tenant_coherence(
    sender: type[models.Model],
    instance: models.Model,
    operation: str,
) -> None:
    """Validate that a model instance's tenant matches the active context.

    Raises:
        MissingTenantContextError: if no tenant context is active.
        CrossTenantAccessError: if the instance's tenant_id differs from
            the active context's tenant_id.
    """
    if _signal_bypass_var.get():
        # ADR-0013 mode 3 -- ``_unsafe_unscoped`` bypass. Audit emission
        # happens at the manager level before the bypass scope is entered.
        return

    ctx = try_current_tenant()
    if ctx is None:
        raise MissingTenantContextError(
            operation=f"{operation}.{sender.__qualname__}",
            stack_context={"hint": "No tenant context active for write operation."},
        )

    tenant_field = default_registry.get(sender).tenant_field
    instance_tenant = getattr(instance, tenant_field, None)

    if not instance_tenant:
        # Auto-fill: set the instance's tenant_id from the active context when
        # missing. "Missing" includes None, "" (default for CharField without
        # default=), 0, or any falsy value -- whatever Django defaults the
        # field type to when the user did not specify a value. Only on
        # creation (pk is None); on update, a falsy tenant_id is suspicious
        # enough to surface as a cross-tenant access.
        if instance.pk is None:
            setattr(instance, tenant_field, ctx.tenant_id)
            return
        raise CrossTenantAccessError(
            tenant_id_expected=ctx.tenant_id,
            tenant_id_actual=None,
            model=sender.__qualname__,
            operation=f"{operation}.{sender.__qualname__}",
        )

    if str(instance_tenant) != str(ctx.tenant_id):
        raise CrossTenantAccessError(
            tenant_id_expected=ctx.tenant_id,
            tenant_id_actual=TenantId(str(instance_tenant)),
            model=sender.__qualname__,
            operation=f"{operation}.{sender.__qualname__}",
        )


def _pre_save_handler(
    sender: type[models.Model],
    instance: models.Model,
    **kwargs: object,  # noqa: ARG001
) -> None:
    _validate_tenant_coherence(sender, instance, "pre_save")


def _pre_delete_handler(
    sender: type[models.Model],
    instance: models.Model,
    **kwargs: object,  # noqa: ARG001
) -> None:
    _validate_tenant_coherence(sender, instance, "pre_delete")


def connect_signals(model: type[models.Model]) -> None:
    """Connect pre_save/pre_delete signals for a tenant-aware model.

    Called by @tenant_aware decorator (Sub-phase 2A) after model registration.
    """
    # django-stubs declares Signal.connect with `receiver: (...) -> Unknown`,
    # which pyright cannot narrow even though our handlers are concrete.
    pre_save.connect(_pre_save_handler, sender=model)  # pyright: ignore[reportUnknownMemberType]
    pre_delete.connect(_pre_delete_handler, sender=model)  # pyright: ignore[reportUnknownMemberType]
