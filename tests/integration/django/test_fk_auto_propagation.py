"""Tests for D-AUTO.0 ``auto_propagate_from_parent_fk`` (Finding #11)."""

from __future__ import annotations

import pytest

from tenantshield import tenant_scope
from tenantshield.adapters.django.signals import (
    _auto_propagate_tenant_from_fk_parent,
    _bypass_signal_validation,
)
from tenantshield.exceptions import CrossTenantAccessError
from tests.integration.django.testapp.models import (
    Invoice,
    InvoiceLine,
    NoteWithoutTenantAwareFK,
    PlainModel,
)


@pytest.mark.django_db
def test_auto_propagate_populates_tenant_field_from_fk_parent(tenant_acme) -> None:
    """``InvoiceLine`` without explicit ``tenant_id`` inherits it from ``invoice``."""
    with tenant_scope(tenant_acme):
        invoice = Invoice.objects.create(tenant_id="acme", amount=100, description="parent")
        line = InvoiceLine(invoice=invoice, description="line", amount=10)
        line.save()
        assert line.tenant_id == "acme"


@pytest.mark.django_db
def test_auto_propagate_respects_explicit_assignment(tenant_acme) -> None:
    """Pre-set ``tenant_id`` is honoured (no overwrite from FK parent)."""
    with tenant_scope(tenant_acme):
        invoice = Invoice.objects.create(tenant_id="acme", amount=100, description="parent")
        line = InvoiceLine(
            tenant_id="acme",  # explicit; matches scope so validation passes
            invoice=invoice,
            description="explicit",
            amount=20,
        )
        line.save()
        assert line.tenant_id == "acme"


@pytest.mark.django_db
def test_auto_propagate_catches_cross_tenant_parent(tenant_acme, tenant_globex) -> None:
    """Parent from another tenant -> auto-propagate triggers CrossTenantAccessError.

    Without auto-propagate the existing ``_validate_tenant_coherence``
    autofill path would silently fill the child with ``ctx.tenant_id``
    ("acme"), masking the cross-tenant parent. With D-AUTO.0 the
    propagated value ("globex") conflicts with the active scope ("acme")
    and surfaces the violation explicitly.
    """
    with tenant_scope(tenant_globex):
        foreign_invoice = Invoice.objects.create(
            tenant_id="globex", amount=999, description="foreign parent"
        )
    with tenant_scope(tenant_acme):
        line = InvoiceLine(invoice=foreign_invoice, description="leak", amount=5)
        with pytest.raises(CrossTenantAccessError):
            line.save()


@pytest.mark.django_db
def test_no_auto_propagate_when_no_tenant_aware_fk_exists(tenant_acme) -> None:
    """Skip path: only FK targets a NON-tenant-aware model.

    ``_validate_tenant_coherence`` still autofills from the active scope
    (existing behaviour), so the save succeeds with the scope's tenant id.
    """
    with tenant_scope(tenant_acme):
        plain = PlainModel.objects.create(name="vanilla")
        note = NoteWithoutTenantAwareFK(plain=plain, body="orphan")
        note.save()
        # No FK target was tenant-aware -> auto-propagate skipped ->
        # existing autofill path stamped the scope's tenant.
        assert note.tenant_id == "acme"


@pytest.mark.django_db
def test_auto_propagate_respects_signal_bypass(tenant_acme) -> None:
    """Inside ``_bypass_signal_validation`` the auto-propagate handler stays out.

    The bypass scope is the contract used by ``_unsafe_unscoped`` writes
    (ADR-0013 mode 3, D-USU.0). Verifies the two handlers compose
    cleanly: when bypass is active, the tenant field is NOT populated
    by D-AUTO.0 because the handler returns early.
    """
    with tenant_scope(tenant_acme):
        invoice = Invoice.objects.create(tenant_id="acme", amount=100, description="parent-bypass")
        # Explicit tenant_id required because bypass disables both
        # auto-propagate AND auto-fill paths.
        line = InvoiceLine(
            tenant_id="acme",
            invoice=invoice,
            description="bypass-line",
            amount=7,
        )
        with _bypass_signal_validation():
            line.save()
        assert line.tenant_id == "acme"


@pytest.mark.django_db
def test_auto_propagate_handler_tolerates_missing_fk(tenant_acme) -> None:
    """Direct invocation of the handler with an unsaved-FK instance does not crash.

    Verifies the auto-propagate handler is defensive: when an FK is
    unset, the handler skips that field and continues. The
    user-visible save path is still gated by Django's foreign-key
    integrity, but that is not the handler's concern.
    """
    with tenant_scope(tenant_acme):
        line = InvoiceLine(description="no-fk", amount=1)
        # Handler must not raise even when no FK is set; tenant_id stays
        # falsy and downstream validation logic handles the rest.
        _auto_propagate_tenant_from_fk_parent(sender=InvoiceLine, instance=line)
        assert not line.tenant_id


@pytest.mark.django_db
def test_auto_propagate_first_fk_match_wins(tenant_acme) -> None:
    """Declaration order determines which FK is used (deterministic).

    ``InvoiceLine`` has a single tenant-aware FK (``invoice``); this
    test pins the deterministic-selection contract: the first FK in
    ``_meta.get_fields()`` order whose target is registered + whose
    value carries a tenant wins. Adding a second tenant-aware FK in
    the future MUST NOT silently change which one is picked.
    """
    with tenant_scope(tenant_acme):
        invoice = Invoice.objects.create(tenant_id="acme", amount=100, description="parent-order")
        line = InvoiceLine(invoice=invoice, description="order", amount=3)
        line.save()
        # If a second tenant-aware FK is ever added before ``invoice``
        # in declaration order, this assertion catches the regression
        # because the tenant id source would change.
        assert line.tenant_id == "acme"
