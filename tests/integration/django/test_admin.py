"""Tests for D-ADM.0 ``TenantAwareAdmin`` mixin (Finding #4 LOW)."""

from __future__ import annotations

from unittest.mock import Mock

from django.contrib import admin

from tenantshield.adapters.django import TenantAwareAdmin
from tests.integration.django.testapp.models import Invoice, Org, PlainModel


def _build_admin(model: type) -> TenantAwareAdmin:
    """Build an isolated ``TenantAwareAdmin`` for a model without registering it."""
    return TenantAwareAdmin(model, admin.AdminSite())  # type: ignore[arg-type]


def test_tenant_field_prepended_when_registered() -> None:
    """The registered tenant field is the first entry in ``get_list_filter``."""
    invoice_admin = _build_admin(Invoice)
    request = Mock()
    filters = list(invoice_admin.get_list_filter(request))
    assert filters[0] == "tenant_id"


def test_custom_tenant_field_respected() -> None:
    """A model with ``tenant_field="org_id"`` uses that field in the filter."""
    org_admin = _build_admin(Org)
    request = Mock()
    filters = list(org_admin.get_list_filter(request))
    assert filters[0] == "org_id"


def test_no_duplicate_when_field_already_listed() -> None:
    """If the subclass already lists the tenant field, it is not duplicated."""

    class InvoiceAdminWithFilter(TenantAwareAdmin):
        list_filter = ("tenant_id", "amount")  # tenant_id pre-listed

    instance = InvoiceAdminWithFilter(Invoice, admin.AdminSite())  # type: ignore[arg-type]
    filters = list(instance.get_list_filter(Mock()))
    # Count occurrences -- must be exactly one.
    assert filters.count("tenant_id") == 1


def test_plain_model_unaffected() -> None:
    """A non-tenant-aware model gets the parent ``ModelAdmin`` behaviour."""
    plain_admin = _build_admin(PlainModel)
    request = Mock()
    filters = list(plain_admin.get_list_filter(request))
    assert "tenant_id" not in filters
