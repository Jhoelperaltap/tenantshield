"""@tenant_aware decorator for Django models."""

from __future__ import annotations

from typing import TYPE_CHECKING, overload

from django.db import models

from tenantshield.exceptions import ConfigurationError
from tenantshield.registry import default_registry

if TYPE_CHECKING:
    from collections.abc import Callable


@overload
def tenant_aware(model: type[models.Model], /) -> type[models.Model]: ...
@overload
def tenant_aware(
    model: None = None,
    /,
    *,
    tenant_field: str = ...,
    manager_class: type[models.Manager[models.Model]] | None = ...,
) -> Callable[[type[models.Model]], type[models.Model]]: ...


def tenant_aware(
    model: type[models.Model] | None = None,
    /,
    *,
    tenant_field: str = "tenant_id",
    manager_class: type[models.Manager[models.Model]] | None = None,
) -> type[models.Model] | Callable[[type[models.Model]], type[models.Model]]:
    """Mark a Django model as tenant-aware.

    The decorator: (1) registers the model in TenantShield's default
    registry, (2) installs ``TenantAwareManager`` as the model's default
    manager (raising ``ConfigurationError`` if the model already has a
    custom manager and ``manager_class`` is not provided), (3) installs
    ``_unscoped`` as an escape-hatch manager.

    Examples:
        Basic usage::

            @tenant_aware
            class Invoice(models.Model):
                tenant_id = models.CharField(max_length=64)
                amount = models.DecimalField(max_digits=10, decimal_places=2)

        Custom tenant field name::

            @tenant_aware(tenant_field="org_id")
            class Org(models.Model):
                org_id = models.CharField(max_length=64)

    Args:
        model: The model class to decorate. If None, returns a decorator.
        tenant_field: Name of the field carrying the tenant id. Default: ``tenant_id``.
        manager_class: Optional manager class to compose with TenantAwareManager.
            Reserved for Sub-phase 2A.X; raises NotImplementedError if provided.

    Raises:
        ConfigurationError: if the model already has a custom default manager
            and ``manager_class`` is not provided.
    """
    # Imported here to break the import cycle with managers.py importing
    # from registry which is imported from here.
    from tenantshield.adapters.django.managers import TenantAwareManager  # noqa: PLC0415

    def _wrap(cls: type[models.Model]) -> type[models.Model]:
        if manager_class is not None:
            msg = (
                "Composition with custom manager_class is not implemented in "
                "Sub-phase 2A. Will be added when a real use case appears."
            )
            raise NotImplementedError(msg)

        # cls._meta is Django's documented introspection API (public by contract).
        # Manager[Unknown] is unavoidable here because models.Model is abstract;
        # the concrete tenant-aware classes resolved at decoration time carry
        # their own Manager parametrization, which django-stubs cannot statically
        # follow through `type[models.Model]`.
        local_managers = cls._meta.local_managers  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        for mgr in local_managers:  # pyright: ignore[reportUnknownVariableType]
            mgr_type = type(mgr)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
            if mgr_type is not models.Manager:
                msg = (
                    f"Model {cls.__qualname__!r} already has a custom manager "
                    f"{mgr_type.__qualname__!r}. Pass manager_class=... to "
                    f"compose with TenantAwareManager (not yet implemented in "
                    f"Sub-phase 2A)."
                )
                raise ConfigurationError(msg)

        # Register in the core registry.
        default_registry.register(cls, tenant_field=tenant_field)

        # Install TenantAwareManager + _unscoped escape hatch.
        cls.add_to_class("objects", TenantAwareManager())
        cls.add_to_class("_unscoped", models.Manager())

        # Connect pre_save/pre_delete signals for write-path validation.
        # Deferred import for consistency with the TenantAwareManager import
        # above; both modules live in the same package and could be top-level,
        # but the symmetry is intentional.
        from tenantshield.adapters.django.signals import connect_signals  # noqa: PLC0415

        connect_signals(cls)

        return cls

    if model is None:
        return _wrap
    return _wrap(model)
