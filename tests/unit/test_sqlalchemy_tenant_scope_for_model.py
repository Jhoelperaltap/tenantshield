"""Tests for SA ``tenant_scope_for_model`` DX shortcut (SA Cat 3 parity)."""

from __future__ import annotations

import pytest

from tenantshield import current_tenant, try_current_tenant
from tenantshield.adapters.sqlalchemy import tenant_scope_for_model


class _FakeInstance:
    """Minimal SA-mapped-like stand-in with an ``id`` attribute."""

    def __init__(self, instance_id: object) -> None:
        self.id = instance_id


def test_tenant_scope_for_model_binds_current_tenant() -> None:
    """Inside the block, ``current_tenant()`` returns the instance-derived context."""
    instance = _FakeInstance(instance_id=42)
    with tenant_scope_for_model(instance):
        ctx = current_tenant()
        assert ctx.tenant_id == "42"


def test_tenant_scope_for_model_accepts_string_id() -> None:
    """String ids are preserved verbatim (no double conversion)."""
    instance = _FakeInstance(instance_id="acme-tenant")
    with tenant_scope_for_model(instance):
        assert current_tenant().tenant_id == "acme-tenant"


def test_tenant_scope_for_model_rejects_none() -> None:
    """``None`` instance raises ``ValueError``."""
    with pytest.raises(ValueError, match="non-None"), tenant_scope_for_model(None):
        pass  # pragma: no cover


def test_tenant_scope_for_model_rejects_object_without_id() -> None:
    """Objects without an ``id`` attribute raise ``ValueError``."""

    class WithoutId:
        pass

    with pytest.raises(ValueError, match="'id' attribute"), tenant_scope_for_model(WithoutId()):
        pass  # pragma: no cover


def test_tenant_scope_for_model_releases_context_on_exit() -> None:
    """Exiting the block clears the bound tenant (no leakage)."""
    assert try_current_tenant() is None
    with tenant_scope_for_model(_FakeInstance(instance_id=7)):
        assert try_current_tenant() is not None
    assert try_current_tenant() is None
