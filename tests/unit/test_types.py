"""Tests for tenantshield._types."""

from __future__ import annotations

from tenantshield._types import TenantId


def test_tenant_id_is_str_at_runtime() -> None:
    tid = TenantId("acme")
    assert isinstance(tid, str)
    assert tid == "acme"


def test_tenant_id_equality_by_value() -> None:
    assert TenantId("acme") == TenantId("acme")
    assert TenantId("acme") != TenantId("globex")


def test_tenant_id_no_normalization() -> None:
    # Confirms the documented contract: no implicit normalization.
    assert TenantId("Acme") != TenantId("acme")
    assert TenantId(" acme") != TenantId("acme")
