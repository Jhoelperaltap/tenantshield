"""Tests for D-MIG.0 migration metadata helpers (Finding #3 LOW)."""

from __future__ import annotations

from tenantshield.adapters.django import (
    TenantAwareModelMetadata,
    get_model_metadata,
    tenant_aware_models,
)
from tests.integration.django.testapp.models import (
    Invoice,
    InvoiceLine,
    PlainModel,
)


def test_tenant_aware_models_yields_registered_entries() -> None:
    """Every registered tenant-aware model surfaces via the helper."""
    metas = {meta.model_qualname: meta for meta in tenant_aware_models()}
    assert "tests.integration.django.testapp.models.Invoice" in metas
    assert "tests.integration.django.testapp.models.Org" in metas
    # The org_id custom tenant_field is captured.
    assert metas["tests.integration.django.testapp.models.Org"].tenant_field == "org_id"


def test_get_model_metadata_for_registered_returns_snapshot() -> None:
    """The lookup returns a frozen dataclass with the registered tenant_field."""
    meta = get_model_metadata(Invoice)
    assert meta is not None
    assert isinstance(meta, TenantAwareModelMetadata)
    assert meta.tenant_field == "tenant_id"
    assert meta.model_qualname.endswith("Invoice")


def test_get_model_metadata_for_plain_model_returns_none() -> None:
    """Non-tenant-aware models are signalled by ``None`` (caller branch hint)."""
    assert get_model_metadata(PlainModel) is None


def test_auto_propagate_flag_surfaces_when_enabled() -> None:
    """``auto_propagate_from_parent_fk=True`` flag is captured in the snapshot."""
    meta = get_model_metadata(InvoiceLine)
    assert meta is not None
    assert meta.auto_propagate_from_parent_fk is True
    # Invoice does NOT have auto-propagate; pin the default for
    # downstream introspection.
    invoice_meta = get_model_metadata(Invoice)
    assert invoice_meta is not None
    assert invoice_meta.auto_propagate_from_parent_fk is False
    # Default for audit flag also pinned (Invoice has neither audit nor
    # auto-propagate).
    assert invoice_meta.audit_cross_tenant_attempts is False
