"""Tests for pre_save/pre_delete signal handlers (write-path validation)."""

from __future__ import annotations

import pytest

from tenantshield import tenant_scope
from tenantshield.exceptions import CrossTenantAccessError, MissingTenantContextError
from tests.integration.django.testapp.models import Invoice


@pytest.mark.django_db
def test_save_with_tenant_succeeds(tenant_acme) -> None:
    """Saving an instance with matching tenant succeeds."""
    with tenant_scope(tenant_acme):
        invoice = Invoice(tenant_id="acme", amount=100, description="test")
        invoice.save()
        assert invoice.pk is not None


@pytest.mark.django_db
def test_save_autofills_tenant_id_on_create(tenant_acme) -> None:
    """Saving without tenant_id auto-fills from active context (only on create)."""
    with tenant_scope(tenant_acme):
        invoice = Invoice(amount=100, description="autofill test")
        invoice.save()
        assert invoice.tenant_id == "acme"


@pytest.mark.django_db
def test_save_raises_without_context() -> None:
    """Saving without an active tenant_scope raises MissingTenantContextError."""
    invoice = Invoice(tenant_id="acme", amount=100, description="no scope")
    with pytest.raises(MissingTenantContextError):
        invoice.save()


@pytest.mark.django_db
def test_save_raises_on_cross_tenant_write(tenant_acme) -> None:
    """Saving with tenant_id mismatching active context raises CrossTenantAccessError."""
    with tenant_scope(tenant_acme):
        invoice = Invoice(tenant_id="globex", amount=100, description="cross-tenant")
        with pytest.raises(CrossTenantAccessError):
            invoice.save()


@pytest.mark.django_db
def test_delete_raises_on_cross_tenant(invoices, tenant_acme) -> None:  # noqa: ARG001
    """Deleting an invoice belonging to another tenant raises CrossTenantAccessError."""
    # _unscoped is the documented escape-hatch manager API (read-only).
    globex_invoice = Invoice._unscoped.filter(tenant_id="globex").first()  # noqa: SLF001
    assert globex_invoice is not None

    with tenant_scope(tenant_acme), pytest.raises(CrossTenantAccessError):
        globex_invoice.delete()


@pytest.mark.django_db
def test_update_existing_with_cleared_tenant_id_raises(invoices, tenant_acme) -> None:  # noqa: ARG001
    """Updating an instance with cleared tenant_id raises CrossTenantAccessError.

    The signal handler's auto-fill semantics treat falsy values (None, "", 0)
    as "missing tenant_id". On create (pk is None), missing triggers auto-fill
    from the active context. On update (pk is not None), missing is suspicious
    and raises CrossTenantAccessError indicating the instance lost its tenant
    association.
    """
    with tenant_scope(tenant_acme):
        invoice = Invoice.objects.first()
        assert invoice is not None
        invoice.tenant_id = ""  # cleared but not None; pk is set.
        with pytest.raises(CrossTenantAccessError):
            invoice.save()
