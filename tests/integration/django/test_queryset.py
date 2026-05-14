"""Tests for TenantAwareQuerySet."""

from __future__ import annotations

import pytest

from tenantshield import tenant_scope
from tests.integration.django.testapp.models import Invoice


@pytest.mark.django_db
def test_filter_chains_preserve_tenant_filter(invoices, tenant_acme):  # noqa: ARG001
    """Chained filters maintain the tenant scope."""
    with tenant_scope(tenant_acme):
        result = list(
            Invoice.objects.filter(amount__gt=50).filter(description__contains="acme"),
        )
    assert len(result) == 2
    assert all(inv.tenant_id == "acme" for inv in result)


@pytest.mark.django_db
def test_exclude_respects_tenant(invoices, tenant_acme):  # noqa: ARG001
    """exclude() maintains the tenant filter."""
    with tenant_scope(tenant_acme):
        result = list(Invoice.objects.exclude(amount=100))
    assert len(result) == 1
    assert result[0].tenant_id == "acme"
    assert result[0].amount == 200


@pytest.mark.django_db
def test_update_respects_tenant(invoices, tenant_acme):  # noqa: ARG001
    """update() only affects invoices in the active tenant."""
    with tenant_scope(tenant_acme):
        affected = Invoice.objects.filter(amount__gt=0).update(description="updated")
    assert affected == 2

    # _unscoped is the documented escape-hatch manager API.
    globex_invoice = Invoice._unscoped.filter(tenant_id="globex").first()  # noqa: SLF001
    assert globex_invoice is not None
    assert globex_invoice.description == "globex-1"


@pytest.mark.django_db
def test_delete_respects_tenant(invoices, tenant_acme):  # noqa: ARG001
    """delete() only affects invoices in the active tenant."""
    with tenant_scope(tenant_acme):
        deleted_count, _ = Invoice.objects.filter(amount__gt=0).delete()
    assert deleted_count == 2

    # _unscoped is the documented escape-hatch manager API.
    assert Invoice._unscoped.filter(tenant_id="globex").count() == 1  # noqa: SLF001


@pytest.mark.django_db
def test_exists_respects_tenant(invoices, tenant_acme):  # noqa: ARG001
    """exists() reflects only the active tenant's data."""
    with tenant_scope(tenant_acme):
        assert Invoice.objects.filter(amount=300).exists() is False
        assert Invoice.objects.filter(amount=100).exists() is True


@pytest.mark.django_db
def test_double_filter_application_prevented(invoices, tenant_acme):  # noqa: ARG001
    """The _tenant_filter_applied flag prevents double tenant_id injection."""
    with tenant_scope(tenant_acme):
        qs = Invoice.objects.filter(amount__gt=0)
        # _tenant_filter_applied is package-internal state inspected for
        # regression testing of the double-injection guard.
        assert qs._tenant_filter_applied is True  # noqa: SLF001
        qs2 = qs.filter(description__contains="acme")
        assert qs2._tenant_filter_applied is True  # noqa: SLF001
        # SELECT lists tenant_id as a column; counting "tenant_id" alone
        # matches both SELECT and WHERE. The pattern '"tenant_id" = ' is
        # specific to WHERE filters (Django formats them with spaces around
        # the operator). The bug we guard against would produce two such
        # WHERE clauses; we expect exactly one.
        sql_str = str(qs2.query)
        where_filters_on_tenant = sql_str.count('"tenant_id" = ')
        assert where_filters_on_tenant == 1
