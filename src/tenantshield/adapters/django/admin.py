"""Django admin integration for ``@tenant_aware`` models.

Per Finding #4 (Counterbook ADR-0015 catalog): out of the box, the
Django admin list view for a tenant-aware model does not surface a
tenant filter. Adopter teams routinely paste boilerplate into every
``ModelAdmin`` subclass to add the tenant id to ``list_filter``. This
module ships ``TenantAwareAdmin``, a mixin that wires that filter
automatically based on the model's registered ``tenant_field``.

The mixin is opt-in: adopters compose it into their own admin classes
when they want the filter surfaced. It does NOT replace
``admin.ModelAdmin``; it composes with it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib import admin

from tenantshield.registry import default_registry

if TYPE_CHECKING:
    from django.http import HttpRequest


class TenantAwareAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """``ModelAdmin`` mixin that auto-includes the tenant field as a list filter.

    Usage:

        from tenantshield.adapters.django import TenantAwareAdmin
        from django.contrib import admin

        @admin.register(Invoice)
        class InvoiceAdmin(TenantAwareAdmin):
            list_display = ("amount", "description")

    The mixin overrides ``get_list_filter`` to prepend the registered
    ``tenant_field``. If the subclass already lists the field, it is
    not duplicated. If the model is not registered tenant-aware, the
    behaviour is identical to plain ``admin.ModelAdmin`` (defensive
    fallback so the mixin never breaks admin loading).
    """

    # django-stubs declares get_list_filter as returning a complex union
    # (Field / str / tuple / type[ListFilter] / list). The mixin returns a
    # tuple of the same value space; ``tuple[Any, ...]`` keeps both type
    # checkers quiet without over-narrowing the contract.
    def get_list_filter(self, request: HttpRequest) -> tuple[Any, ...]:
        parent_filters: tuple[Any, ...] = tuple(super().get_list_filter(request))  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType, reportUnknownVariableType]
        model = self.model  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not default_registry.is_registered(model):  # pyright: ignore[reportUnknownArgumentType]
            return parent_filters
        tenant_field = default_registry.get(model).tenant_field  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
        if tenant_field in parent_filters:
            return parent_filters
        return (tenant_field, *parent_filters)
