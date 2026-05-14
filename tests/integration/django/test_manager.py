"""Tests for TenantAwareManager."""

from __future__ import annotations

import pytest

from tenantshield import tenant_scope
from tenantshield.adapters.django.managers import TenantAwareManager
from tenantshield.exceptions import MissingTenantContextError
from tests.integration.django.testapp.models import Invoice


@pytest.mark.django_db
def test_objects_is_tenant_aware_manager(invoices):  # noqa: ARG001
    """Verify the decorator installed TenantAwareManager as the default manager.

    Regression test for the bug fixed in commit 578652c, where the decorator
    failed to replace Django's auto-created plain Manager, leaving Invoice.objects
    as a plain Manager that bypassed tenant filtering entirely.
    """
    assert isinstance(Invoice.objects, TenantAwareManager)
    assert type(Invoice.objects).__name__ == "TenantAwareManager"


@pytest.mark.django_db
def test_all_filters_by_tenant(invoices, tenant_acme):  # noqa: ARG001
    """Invoice.objects.all() returns only the active tenant's invoices."""
    with tenant_scope(tenant_acme):
        result = list(Invoice.objects.all())
    assert len(result) == 2
    assert all(inv.tenant_id == "acme" for inv in result)


@pytest.mark.django_db
def test_all_raises_without_context(invoices):  # noqa: ARG001
    """Invoice.objects.all() raises when no tenant context is active."""
    with pytest.raises(MissingTenantContextError):
        list(Invoice.objects.all())


@pytest.mark.django_db
def test_get_filters_by_tenant(invoices, tenant_acme):  # noqa: ARG001
    """Invoice.objects.get(pk=other_tenant_pk) raises DoesNotExist."""
    # _unscoped is the documented escape-hatch manager API.
    globex_invoice = Invoice._unscoped.filter(tenant_id="globex").first()  # noqa: SLF001
    assert globex_invoice is not None

    with tenant_scope(tenant_acme), pytest.raises(Invoice.DoesNotExist):
        Invoice.objects.get(pk=globex_invoice.pk)


@pytest.mark.django_db
def test_count_respects_scope(invoices, tenant_acme):  # noqa: ARG001
    """Invoice.objects.count() counts only the active tenant's invoices."""
    with tenant_scope(tenant_acme):
        count = Invoice.objects.count()
    assert count == 2


@pytest.mark.django_db
def test_unscoped_bypasses_filter(invoices):  # noqa: ARG001
    """Invoice._unscoped.all() returns all invoices regardless of tenant."""
    # _unscoped is the documented escape-hatch manager API.
    result = list(Invoice._unscoped.all())  # noqa: SLF001
    assert len(result) == 3
