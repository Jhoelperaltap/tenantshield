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

    def update(self, **kwargs: object) -> int:
        # ADR-0013 + Finding #1 (SOC2 BLOCKER): when audit_cross_tenant_attempts
        # is enabled on the model, detect cross-tenant PKs that match the user's
        # filters but belong to other tenants. Detection is pre-flight (before
        # the SQL UPDATE executes) so the audit event captures the attempt even
        # when the operation yields zero affected rows.
        _maybe_emit_cross_tenant_violation(self, "update")
        return super().update(**kwargs)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    def delete(self) -> tuple[int, dict[str, int]]:
        _maybe_emit_cross_tenant_violation(self, "delete")
        return super().delete()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


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


# ADR-0013 + Finding #1 (SOC2 BLOCKER) -- cross-tenant audit detection.
#
# When a model is decorated with ``@tenant_aware(audit_cross_tenant_attempts=True)``,
# every ``Model.objects.filter(...).update(...)`` and ``.delete()`` call
# performs a pre-flight check: clone the queryset's query, strip the tenant
# filter from the WHERE tree, execute against ``Model._unscoped`` with an
# explicit ``exclude(tenant_field=current)`` to find PKs that match the
# user's other filters but belong to OTHER tenants. If any are found, emit
# ``ENFORCEMENT_VIOLATION`` with the attempted PKs + caller stack frames.
#
# This catches the SOC2 attack vector: an actor iterating PKs in an update
# or delete to probe other tenants. Currently the SQL ``WHERE tenant_id=X
# AND pk=N`` simply returns 0 affected rows when ``pk=N`` belongs to a
# different tenant; the actor learns nothing and leaves no forensic trace.
# With audit enabled, every such attempt generates an observable audit
# event that SIEM tooling can detect.
#
# OFF by default per ADR-0013 + adopter noise management. Enable per-model
# for compliance posture (SOC2 Type II, PCI-DSS).


def _strip_clauses_for_field(where_node: object, field_name: str) -> None:
    """Recursively remove WHERE clauses referencing ``field_name`` from a tree.

    Mutates ``where_node.children`` in place. Used to build a sibling query
    that has the user's filters minus the tenant filter, so we can detect
    cross-tenant matches against ``Model._unscoped``.

    Django-internal API surface (WhereNode + Lookup); defensive against
    upstream changes (caller wraps in try/except).
    """
    children = getattr(where_node, "children", None)
    if children is None:
        return
    new_children: list[object] = []
    for child in children:  # pyright: ignore[reportUnknownVariableType]
        if hasattr(child, "children"):
            _strip_clauses_for_field(child, field_name)
            inner = getattr(child, "children", None)
            if inner:
                new_children.append(child)  # pyright: ignore[reportUnknownArgumentType]
            continue
        target_col: str | None = None
        lhs = getattr(child, "lhs", None)
        if lhs is not None:
            target = getattr(lhs, "target", None)
            if target is not None:
                target_col = getattr(target, "column", None) or getattr(target, "name", None)
        if target_col != field_name:
            new_children.append(child)  # pyright: ignore[reportUnknownArgumentType]
    where_node.children = new_children  # type: ignore[attr-defined]


def _maybe_emit_cross_tenant_violation(
    qs: models.QuerySet,  # type: ignore[type-arg]
    operation: str,
) -> None:
    """Pre-flight detect cross-tenant ``update``/``delete`` attempts.

    Inspects the model class for the ``_tenantshield_audit_cross_tenant``
    flag set by ``@tenant_aware(audit_cross_tenant_attempts=True)``. When
    set, builds a sibling queryset against ``Model._unscoped`` with the
    same user filters but the tenant clause stripped + an explicit
    exclusion of the current tenant. PKs returned by that sibling are
    cross-tenant attempts and trigger ``ENFORCEMENT_VIOLATION`` emission.

    Defensive against query manipulation failures: any exception in the
    detection path is swallowed so the user's intended operation always
    runs to completion.
    """
    model = qs.model  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not getattr(model, "_tenantshield_audit_cross_tenant", False):  # pyright: ignore[reportUnknownArgumentType]
        return
    ctx = try_current_tenant()
    if ctx is None:
        return
    tenant_field = default_registry.get(model).tenant_field  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    try:
        cloned_query = qs.query.clone()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        _strip_clauses_for_field(cloned_query.where, tenant_field)  # pyright: ignore[reportUnknownMemberType]
        unscoped_manager = model._unscoped  # noqa: SLF001  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType, reportUnknownVariableType]
        unscoped_qs: models.QuerySet = unscoped_manager.all()  # type: ignore[type-arg]  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAssignmentType]
        unscoped_qs.query = cloned_query  # pyright: ignore[reportUnknownMemberType]
        other_tenant_qs = unscoped_qs.exclude(**{tenant_field: ctx.tenant_id})  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        other_tenant_pks: list[object] = sorted(other_tenant_qs.values_list("pk", flat=True))  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType, reportUnknownVariableType]
    except Exception:
        # Defensive: never break the user's operation due to detection issues.
        return
    if not other_tenant_pks:
        return
    _emit_enforcement_violation_audit(
        model=model,  # pyright: ignore[reportUnknownArgumentType]
        operation=operation,
        attempted_pks=other_tenant_pks,
    )


def _emit_enforcement_violation_audit(
    model: type[models.Model],
    operation: str,
    attempted_pks: list[object],
) -> None:
    """Dispatch ``ENFORCEMENT_VIOLATION`` to the audit bus for cross-tenant attempts.

    Companion to ``_emit_enforcement_bypass_audit`` (ADR-0013 mode 3 audit
    helper) and ``_emit_enforcement_violation_audit`` in the SA adapter
    (``adapters/sqlalchemy/events.py``, Sub-fase 5B.5.1). Audit emission
    is gated by the sink registry (independent of observability
    ``configure``) per Decision 7-A separation.

    Args:
        model: The model class on which the cross-tenant attempt occurred.
        operation: ``"update"`` or ``"delete"``.
        attempted_pks: Sorted list of cross-tenant PKs the caller targeted.
    """
    audit_emit(
        AuditEvent(
            event_type=AuditEventType.ENFORCEMENT_VIOLATION,
            tenant_context=try_current_tenant(),
            payload={
                "model_qualname": f"{model.__module__}.{model.__qualname__}",
                "operation": operation,
                "attempted_pks": attempted_pks,
                "caller_stack_frames": traceback.format_stack()[:-2],
            },
        )
    )


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
