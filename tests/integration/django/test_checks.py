"""Tests for TenantShield system checks."""

from __future__ import annotations

from django.db import models

from tenantshield.adapters.django.checks import (
    check_tenant_aware_models_have_tenant_field,
)
from tenantshield.registry import ModelRegistry, default_registry


def test_check_passes_for_valid_models() -> None:
    """Registered testapp models (Invoice, Org) have their declared tenant fields."""
    errors = check_tenant_aware_models_have_tenant_field()
    assert errors == []


def test_check_ignores_non_django_models() -> None:
    """Non-Django classes in the registry are silently skipped by the check."""
    # Local registry for isolation (not the path the check actually iterates),
    # used only to keep the symbol referenced and satisfy linters.
    _ = ModelRegistry()

    class _NotADjangoModel:
        """Plain class without Django _meta -- should be skipped by the check."""

    default_registry.register(_NotADjangoModel)
    try:
        errors = check_tenant_aware_models_have_tenant_field()
        assert errors == []
    finally:
        default_registry.unregister(_NotADjangoModel)


def test_check_reports_error_for_model_missing_tenant_field() -> None:
    """A Django model registered without its tenant field generates Error E001."""

    class _ModelMissingField(models.Model):
        name = models.CharField(max_length=64)

        class Meta:
            app_label = "testapp"

    default_registry.register(_ModelMissingField, tenant_field="tenant_id")
    try:
        errors = check_tenant_aware_models_have_tenant_field()
        matching = [e for e in errors if e.obj is _ModelMissingField]
        assert len(matching) == 1
        error = matching[0]
        assert error.id == "tenantshield.E001"
        assert "_ModelMissingField" in error.msg
        assert "tenant_id" in error.msg
    finally:
        default_registry.unregister(_ModelMissingField)
