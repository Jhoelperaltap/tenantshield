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


def _auto_propagate_tenant_from_fk_parent(
    sender: type[models.Model],
    instance: models.Model,
    **kwargs: object,  # noqa: ARG001
) -> None:
    """Populate the instance tenant field from the first @tenant_aware FK parent.

    ADR-0013 + Finding #11 (Counterbook ADR-0015 catalog). Connected by
    ``connect_signals`` only when ``@tenant_aware(auto_propagate_from_parent_fk=True)``
    is set on the model.

    Behaviour:

    - Skipped when ``_signal_bypass_var`` is active (D-USU.0 ``_unsafe_unscoped``
      compatibility -- bypass operations stay literal).
    - Skipped when the instance tenant field already has a truthy value
      (respect explicit assignment from caller).
    - Iterates ``_meta.get_fields()`` in declaration order; the first
      ``ForeignKey`` whose target model is registered tenant-aware AND whose
      current value carries a tenant id wins. Deterministic.
    - Does not raise on missing FK relations or stale FK values; subsequent
      ``_validate_tenant_coherence`` handles those (MissingTenantContextError
      surfaces normally if no propagation source was found).
    """
    if _signal_bypass_var.get():
        return

    tenant_field = default_registry.get(sender).tenant_field
    if getattr(instance, tenant_field, None):
        return  # Caller already set tenant_field explicitly.

    for field in sender._meta.get_fields():  # noqa: SLF001  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not getattr(field, "many_to_one", False):
            continue
        related_model: type[models.Model] | None = getattr(field, "related_model", None)
        if related_model is None:
            continue
        if not default_registry.is_registered(related_model):
            continue
        fk_value: object = getattr(instance, field.name, None)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        if fk_value is None:
            continue
        parent_tenant_field = default_registry.get(related_model).tenant_field
        parent_tenant = getattr(fk_value, parent_tenant_field, None)
        if parent_tenant:
            setattr(instance, tenant_field, parent_tenant)
            return


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


def connect_signals(
    model: type[models.Model],
    *,
    auto_propagate_from_parent_fk: bool = False,
) -> None:
    """Connect pre_save/pre_delete signals for a tenant-aware model.

    Called by ``@tenant_aware`` decorator after model registration. When
    ``auto_propagate_from_parent_fk`` is True, the auto-propagate handler
    is connected BEFORE the validation handler so that FK-derived tenant
    values are populated in time for coherence validation (Finding #11,
    D-AUTO.0).
    """
    # django-stubs declares Signal.connect with `receiver: (...) -> Unknown`,
    # which pyright cannot narrow even though our handlers are concrete.
    if auto_propagate_from_parent_fk:
        # Connect auto-propagate FIRST so it fires before _pre_save_handler;
        # Django dispatches signal receivers in connection order.
        pre_save.connect(_auto_propagate_tenant_from_fk_parent, sender=model)  # pyright: ignore[reportUnknownMemberType]
    pre_save.connect(_pre_save_handler, sender=model)  # pyright: ignore[reportUnknownMemberType]
    pre_delete.connect(_pre_delete_handler, sender=model)  # pyright: ignore[reportUnknownMemberType]
