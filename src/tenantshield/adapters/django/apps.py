"""Django AppConfig for TenantShield."""

from __future__ import annotations

from django.apps import AppConfig
from django.core import checks


class TenantShieldConfig(AppConfig):
    """AppConfig registering TenantShield with Django.

    Add ``"tenantshield.adapters.django"`` to ``INSTALLED_APPS`` to activate.
    """

    name = "tenantshield.adapters.django"
    label = "tenantshield"
    verbose_name = "TenantShield"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Register system checks and connect signals.

        Called once per Django process at app loading time.
        """
        # Imported here (not at module top) to avoid AppConfig loading-cycle issues.
        from tenantshield.adapters.django import checks as ts_checks  # noqa: PLC0415

        checks.register(ts_checks.check_tenant_aware_models_have_tenant_field)
