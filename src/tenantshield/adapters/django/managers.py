"""Custom Manager and QuerySet for tenant-aware Django models."""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from django.db import models

from tenantshield.adapters.django.signals import (
    _bypass_signal_validation,  # pyright: ignore[reportPrivateUsage]
)
from tenantshield.audit import AuditEvent, AuditEventType
from tenantshield.audit import emit as audit_emit
from tenantshield.context import try_current_tenant
from tenantshield.exceptions import MissingTenantContextError
from tenantshield.registry import default_registry

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable
    from typing import Self


# Generic parametrization of QuerySet/Manager is a documented django-stubs
# limitation when subclassing without binding to a concrete model. The two
# ignores below are arquitectonic: parametrizing to models.QuerySet[models.Model]
# would add no enforcement value and propagate Manager[Unknown] through callers.
class TenantAwareQuerySet(models.QuerySet):  # type: ignore[type-arg]
    """QuerySet that propagates the tenant filter across chained operations.

    The actual injection of ``WHERE tenant_id = <ctx>`` happens in the
    manager's ``get_queryset()``. This class ensures the filter survives
    clone/chain operations (``filter()``, ``exclude()``) and provides the
    contract that allows the manager to mark a queryset as filtered without
    re-injecting on each terminal call.

    The ``_unscoped`` escape hatch on the model bypasses this entirely; its
    usage should be logged to the audit bus and justified in a docstring.
    """

    def __init__(
        self,
        model: type[models.Model] | None = None,
        query: object = None,
        using: str | None = None,
        hints: dict[str, models.Model] | None = None,
    ) -> None:
        # super().__init__ accepts a private Query type for `query`; we widen
        # it to `object` so callers and django-stubs both stay quiet.
        super().__init__(model, query, using, hints)  # type: ignore[arg-type]
        # Prevents double-filtering when QuerySets are cloned through chained
        # operations (e.g. .filter(...).exclude(...).order_by(...)).
        self._tenant_filter_applied: bool = False

    def _clone(self, **kwargs: object) -> Self:
        # Django's _clone is internal but documented as overridable by subclasses
        # that need to preserve custom state across QuerySet copies. django-stubs
        # does not expose it on QuerySet, so both checkers need to be silenced.
        clone: Self = super()._clone(**kwargs)  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
        clone._tenant_filter_applied = self._tenant_filter_applied
        # The Unknown from super()._clone() propagates to the return; the
        # annotated Self does not narrow it for pyright.
        return clone  # pyright: ignore[reportUnknownVariableType]

    def _apply_tenant_filter(self) -> Self:
        if self._tenant_filter_applied:
            return self
        ctx = try_current_tenant()
        if ctx is None:
            # self.model is type[Unknown] under unparametrized QuerySet; the
            # __qualname__ access is safe (type has __qualname__) but pyright
            # cannot prove it.
            model_qualname: str = self.model.__qualname__  # pyright: ignore[reportUnknownMemberType]
            raise MissingTenantContextError(
                operation=f"queryset.{model_qualname}",
                stack_context={
                    "hint": ("No tenant context active. Use bind_tenant() and tenant_scope()."),
                },
            )
        # self.model is type[Unknown] from unparametrized QuerySet; default_registry.get
        # accepts type, so the runtime call is fine even when pyright is uncertain.
        tenant_field = default_registry.get(self.model).tenant_field  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        # Call super().filter to bypass our own override and avoid infinite
        # recursion (our filter() also calls _apply_tenant_filter).
        filtered: Self = super().filter(**{tenant_field: ctx.tenant_id})
        filtered._tenant_filter_applied = True
        return filtered

    def filter(self, *args: object, **kwargs: object) -> Self:
        qs: Self = super().filter(*args, **kwargs)
        return qs._apply_tenant_filter()

    def exclude(self, *args: object, **kwargs: object) -> Self:
        qs: Self = super().exclude(*args, **kwargs)
        return qs._apply_tenant_filter()


# Dynamic base class via from_queryset is the idiomatic Django pattern but
# django-stubs cannot type it through subclassing. The single ignore below
# is arquitectonic, not a missing test.
class TenantAwareManager(models.Manager.from_queryset(TenantAwareQuerySet)):  # type: ignore[misc]
    """Manager that injects the tenant filter at ``get_queryset()`` entry.

    All access to ``Model.objects.*`` (all, count, get, exists, update,
    delete, filter, exclude, etc.) starts from this pre-filtered queryset.
    The plain Django QuerySet inherits the rest of the read/write surface
    unchanged; no recursion-prone overrides on terminal methods.
    """

    use_in_migrations: bool = False

    def get_queryset(self) -> TenantAwareQuerySet:
        """Return a TenantAwareQuerySet with the tenant filter pre-applied.

        If no tenant context is active, raises MissingTenantContextError.
        The ``_unscoped`` escape hatch bypasses this entirely.
        """
        # super().get_queryset() returns the queryset class wired by
        # from_queryset (TenantAwareQuerySet), but django-stubs types it
        # as QuerySet[Unknown] through the dynamic Manager base.
        qs: TenantAwareQuerySet = super().get_queryset()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAssignmentType]
        # _apply_tenant_filter is package-internal API of this module; calling
        # it from the companion Manager class is the documented contract,
        # not external private access.
        return qs._apply_tenant_filter()  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]


# ADR-0013 mode 3 -- ``_unsafe_unscoped`` queryset + manager.
#
# Distinguishing properties vs ``Model.objects`` (mode 1) and
# ``Model._unscoped`` (mode 2):
#
# - No tenant filter (parallel to mode 2).
# - Pre-save / pre-delete signal validation is bypassed for writes
#   (mode 3 unique).
# - Every write emits an ``ENFORCEMENT_BYPASS`` audit event with caller
#   stack context, paralelo the SA adapter's
#   ``_emit_enforcement_violation_audit`` precedent
#   (``adapters/sqlalchemy/events.py:74-105``).
#
# The bypass is implemented as a ``ContextVar`` flag (see
# ``signals.py:_signal_bypass_var``) so async / threaded execution paths
# preserve isolation. Read operations (``filter``, ``all``, etc.) do not
# emit audit events; only writes carry the bypass semantic.


def _emit_enforcement_bypass_audit(
    model: type[models.Model],
    operation: str,
    operation_context: dict[str, object],
) -> None:
    """Dispatch ``ENFORCEMENT_BYPASS`` to the audit bus.

    Companion to ``_emit_enforcement_violation_audit`` in the SA adapter
    (Sub-fase 5B.5.1). Bypass audit emission is gated by the sink
    registry (independent of observability ``configure``) per Decision
    7-A separation. Audit fires unconditionally at every write entry
    point of ``UnsafeUnscopedManager`` / ``UnsafeUnscopedQuerySet``.

    Args:
        model: The model class on which the bypass was exercised.
        operation: One of ``"create"`` / ``"update"`` / ``"delete"`` /
            ``"bulk_create"`` / ``"bulk_update"``.
        operation_context: Operation-specific structured payload (e.g.,
            ``{"count": N}`` for bulk paths, ``{"fields": [...]}`` for
            updates).
    """
    audit_emit(
        AuditEvent(
            event_type=AuditEventType.ENFORCEMENT_BYPASS,
            tenant_context=try_current_tenant(),
            payload={
                "model_qualname": f"{model.__module__}.{model.__qualname__}",
                "operation": operation,
                "operation_context": operation_context,
                "caller_stack_frames": traceback.format_stack()[:-2],
            },
        )
    )


class UnsafeUnscopedQuerySet(models.QuerySet):  # type: ignore[type-arg]
    """QuerySet for ``_unsafe_unscoped``: no tenant filter, audited writes.

    See ADR-0013. Every write operation emits an ``ENFORCEMENT_BYPASS``
    audit event and bypasses ``pre_save``/``pre_delete`` validation where
    applicable. Read operations (``filter``, ``all``, etc.) inherit from
    Django's ``QuerySet`` unchanged.
    """

    def create(self, **kwargs: object) -> models.Model:
        _emit_enforcement_bypass_audit(
            self.model,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            "create",
            {"kwargs_keys": sorted(kwargs.keys())},
        )
        with _bypass_signal_validation():
            # super().create is typed as Any-returning through unparametrized
            # QuerySet; the concrete value is a Model instance per Django
            # contract.
            instance: models.Model = super().create(**kwargs)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAssignmentType]
        return instance  # pyright: ignore[reportUnknownVariableType]

    def update(self, **kwargs: object) -> int:
        _emit_enforcement_bypass_audit(
            self.model,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            "update",
            {"fields_keys": sorted(kwargs.keys())},
        )
        # Django QuerySet.update() does not fire pre_save signals; the
        # ``_bypass_signal_validation`` scope is unnecessary here but
        # harmless if added. Omitted to keep the write path minimal.
        return super().update(**kwargs)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    def delete(self) -> tuple[int, dict[str, int]]:
        _emit_enforcement_bypass_audit(
            self.model,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            "delete",
            {"count_before": self.count()},
        )
        # QuerySet.delete() loads instances and fires pre_delete per
        # instance, so signal bypass is required here.
        with _bypass_signal_validation():
            return super().delete()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    def bulk_create(  # noqa: PLR0913
        self,
        objs: Iterable[models.Model],
        batch_size: int | None = None,
        ignore_conflicts: bool = False,
        update_conflicts: bool = False,
        update_fields: Collection[str] | None = None,
        unique_fields: Collection[str] | None = None,
    ) -> list[models.Model]:
        # Convert to list so len() and pass-through both work; Django
        # iterates objs internally anyway.
        objs_list = list(objs)
        _emit_enforcement_bypass_audit(
            self.model,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            "bulk_create",
            {"count": len(objs_list)},
        )
        # bulk_create does not fire pre_save in Django; bypass scope is
        # unnecessary. Audit emission is the only enforcement signal.
        return super().bulk_create(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            objs_list,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_conflicts=update_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )

    def bulk_update(
        self,
        objs: Iterable[models.Model],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        objs_list = list(objs)
        fields_list = list(fields)
        _emit_enforcement_bypass_audit(
            self.model,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            "bulk_update",
            {"count": len(objs_list), "fields": fields_list},
        )
        return super().bulk_update(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            objs_list,
            fields_list,
            batch_size=batch_size,
        )


class UnsafeUnscopedManager(models.Manager.from_queryset(UnsafeUnscopedQuerySet)):  # type: ignore[misc]
    """Manager for ``_unsafe_unscoped``: no tenant filter, audited writes.

    ADR-0013 mode 3. Installed as ``Model._unsafe_unscoped`` by the
    ``@tenant_aware`` decorator alongside ``Model.objects`` (mode 1) and
    ``Model._unscoped`` (mode 2). Intended for legitimate administrative
    operations only: bulk migrations, periodic Celery tasks, system-level
    housekeeping. Every write emits an ``ENFORCEMENT_BYPASS`` audit event;
    adopters should whitelist call sites with an inline
    ``# ENFORCEMENT_BYPASS: <reason>`` comment per recommended adopter
    policy.
    """

    use_in_migrations: bool = False
