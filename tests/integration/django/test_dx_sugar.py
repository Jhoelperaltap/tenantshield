"""Tests for D-DX.0 sugar layer (Findings #2 + #6)."""

from __future__ import annotations

import pytest

from tenantshield import current_tenant, try_current_tenant
from tenantshield.adapters.django import tenant_scope_for_company
from tenantshield.exceptions import MissingTenantContextError

# ----- Finding #2: MissingTenantContextError hint -----


def test_missing_tenant_context_error_includes_canonical_hint() -> None:
    """Default-generated message includes the canonical-pattern hint."""
    err = MissingTenantContextError(operation="query.all")
    msg = str(err)
    assert "Missing tenant context for operation 'query.all'." in msg
    assert "tenant_scope(bind_tenant(TenantId(str(company.id))))" in msg
    assert "tenant_scope_for_company" in msg


def test_missing_tenant_context_error_serializes_via_to_dict() -> None:
    """``to_dict`` continues to work after hint expansion (no behaviour change)."""
    err = MissingTenantContextError(
        operation="signals.pre_save",
        stack_context={"hint": "diagnostic"},
    )
    data = err.to_dict()
    assert data["type"] == "MissingTenantContextError"
    assert data["operation"] == "signals.pre_save"
    assert data["stack_context"] == {"hint": "diagnostic"}


# ----- Finding #6: tenant_scope_for_company sugar -----


class _FakeCompany:
    """Minimal stand-in for a Django Company model with an ``id`` attribute."""

    def __init__(self, company_id: object) -> None:
        self.id = company_id


def test_tenant_scope_for_company_binds_current_tenant() -> None:
    """Inside the block, ``current_tenant()`` returns the company-derived context."""
    company = _FakeCompany(company_id=42)
    with tenant_scope_for_company(company):
        ctx = current_tenant()
        assert ctx.tenant_id == "42"


def test_tenant_scope_for_company_accepts_string_id() -> None:
    """String ids are preserved verbatim (no double conversion)."""
    company = _FakeCompany(company_id="acme-tenant")
    with tenant_scope_for_company(company):
        assert current_tenant().tenant_id == "acme-tenant"


def test_tenant_scope_for_company_rejects_none() -> None:
    """``None`` company raises ``ValueError``."""
    with pytest.raises(ValueError, match="non-None"), tenant_scope_for_company(None):
        pass  # pragma: no cover


def test_tenant_scope_for_company_rejects_object_without_id() -> None:
    """Objects without an ``id`` attribute raise ``ValueError``."""

    class WithoutId:
        pass

    with pytest.raises(ValueError, match="'id' attribute"), tenant_scope_for_company(WithoutId()):
        pass  # pragma: no cover


def test_tenant_scope_for_company_releases_context_on_exit() -> None:
    """Exiting the block clears the bound tenant (no leakage)."""
    assert try_current_tenant() is None  # baseline
    with tenant_scope_for_company(_FakeCompany(company_id=7)):
        assert try_current_tenant() is not None
    assert try_current_tenant() is None
