"""Custom Manager and QuerySet for tenant-aware Django models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

from tenantshield.context import try_current_tenant
from tenantshield.exceptions import MissingTenantContextError
from tenantshield.registry import default_registry

if TYPE_CHECKING:
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
