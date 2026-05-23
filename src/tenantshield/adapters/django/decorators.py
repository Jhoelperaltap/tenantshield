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
    audit_cross_tenant_attempts: bool = ...,
    auto_propagate_from_parent_fk: bool = ...,
) -> Callable[[type[models.Model]], type[models.Model]]: ...


def tenant_aware(
    model: type[models.Model] | None = None,
    /,
    *,
    tenant_field: str = "tenant_id",
    manager_class: type[models.Manager[models.Model]] | None = None,
    audit_cross_tenant_attempts: bool = False,
    auto_propagate_from_parent_fk: bool = False,
) -> type[models.Model] | Callable[[type[models.Model]], type[models.Model]]:
    """Mark a Django model as tenant-aware.

    The decorator: (1) registers the model in TenantShield's default
    registry, (2) installs ``TenantAwareManager`` as the model's default
    manager (raising ``ConfigurationError`` if the model already has a
    custom manager and ``manager_class`` is not provided), (3) installs
    ``_unscoped`` as an escape-hatch manager, (4) installs
    ``_unsafe_unscoped`` (ADR-0013 mode 3) as the write-escape manager
    that emits ``ENFORCEMENT_BYPASS`` audit events.

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

        Compliance posture (SOC2 / PCI-DSS)::

            @tenant_aware(audit_cross_tenant_attempts=True)
            class CustomerPayment(models.Model):
                tenant_id = models.CharField(max_length=64)
                amount = models.DecimalField(max_digits=10, decimal_places=2)

    Args:
        model: The model class to decorate. If None, returns a decorator.
        tenant_field: Name of the field carrying the tenant id. Default: ``tenant_id``.
        manager_class: Optional manager class to compose with TenantAwareManager.
            Reserved for Sub-phase 2A.X; raises NotImplementedError if provided.
        audit_cross_tenant_attempts: When ``True``, every
            ``Model.objects.filter(...).update(...)`` and ``.delete()``
            performs a pre-flight unscoped query that detects PKs matching
            the caller's other filters but belonging to OTHER tenants. Each
            such attempt emits an ``ENFORCEMENT_VIOLATION`` audit event
            with the attempted PKs + caller stack frames. OFF by default
            per ADR-0013 + adopter noise management. Enable for compliance
            posture (SOC2 Type II, PCI-DSS); resolves Finding #1
            (SOC2 BLOCKER: silent cross-tenant update/delete).
        auto_propagate_from_parent_fk: When ``True``, the ``pre_save``
            signal auto-populates this model's ``tenant_field`` from the
            first ``ForeignKey`` whose target model is also
            ``@tenant_aware`` (declaration order is respected, first match
            wins, deterministic). Skipped when ``tenant_field`` is already
            set (explicit assignment honored) and when ``_signal_bypass_var``
            is active (D-USU.0 compatibility). OFF by default. Eliminates
            boilerplate ``child.company = parent.company`` patterns at
            adopter call sites; resolves Finding #11 (Counterbook
            ADR-0015 catalog).

    Raises:
        ConfigurationError: if the model already has a custom default manager
            and ``manager_class`` is not provided.
    """
    # Imported here to break the import cycle with managers.py importing
    # from registry which is imported from here.
    from tenantshield.adapters.django.managers import (  # noqa: PLC0415
        TenantAwareManager,
        UnsafeUnscopedManager,
    )

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

        # Django auto-creates a plain Manager named "objects" for any model that
        # doesn't define one explicitly. We must remove it before installing
        # TenantAwareManager; otherwise both end up in cls._meta.local_managers
        # and the plain Manager (first-registered) wins as Model.objects.
        cls._meta.local_managers = [
            m
            for m in cls._meta.local_managers  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
            if not (m.name == "objects" and type(m) is models.Manager)  # pyright: ignore[reportUnknownArgumentType]
        ]

        # Install TenantAwareManager + _unscoped read-only escape hatch +
        # _unsafe_unscoped write escape hatch (ADR-0013 three-mode contract).
        cls.add_to_class("objects", TenantAwareManager())
        cls.add_to_class("_unscoped", models.Manager())
        cls.add_to_class("_unsafe_unscoped", UnsafeUnscopedManager())

        # ADR-0013 + Finding #1: store audit configuration on the class. Read
        # at queryset update/delete time by TenantAwareQuerySet to enable
        # cross-tenant attempt detection. Off by default for noise control;
        # enabled per-model for SOC2/PCI-DSS compliance posture.
        cls._tenantshield_audit_cross_tenant = audit_cross_tenant_attempts  # type: ignore[attr-defined]

        # ADR-0013 + Finding #11: store auto-propagate flag on the class.
        # The decision to connect the auto-propagate signal handler is taken
        # below via ``connect_signals``; this attribute exists so adopter
        # introspection (D-MIG.0 migration metadata helpers) can surface the
        # decoration-time choice without inspecting Django signal internals.
        cls._tenantshield_auto_propagate_from_parent_fk = auto_propagate_from_parent_fk  # type: ignore[attr-defined]

        # Connect pre_save/pre_delete signals for write-path validation.
        # Deferred import for consistency with the TenantAwareManager import
        # above; both modules live in the same package and could be top-level,
        # but the symmetry is intentional. ``auto_propagate_from_parent_fk``
        # toggles the FK-parent auto-populate handler (D-AUTO.0, Finding #11).
        from tenantshield.adapters.django.signals import connect_signals  # noqa: PLC0415

        connect_signals(cls, auto_propagate_from_parent_fk=auto_propagate_from_parent_fk)

        return cls

    if model is None:
        return _wrap
    return _wrap(model)
