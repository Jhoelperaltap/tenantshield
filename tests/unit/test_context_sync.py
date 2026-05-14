"""Tests for tenantshield.context (synchronous API)."""

from __future__ import annotations

import dataclasses

import pytest

from tenantshield._types import TenantId
from tenantshield.context import (
    TenantContext,
    bind_tenant,
    current_tenant,
    tenant_scope,
    try_current_tenant,
)
from tenantshield.exceptions import MissingTenantContextError


def test_tenant_context_is_frozen() -> None:
    ctx = TenantContext(tenant_id=TenantId("acme"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.tenant_id = TenantId("globex")  # type: ignore[misc]


def test_tenant_context_equality() -> None:
    a = TenantContext(tenant_id=TenantId("acme"), metadata={"k": "v"})
    b = TenantContext(tenant_id=TenantId("acme"), metadata={"k": "v"})
    assert a == b
    c = TenantContext(tenant_id=TenantId("globex"), metadata={"k": "v"})
    assert a != c


def test_tenant_context_with_metadata() -> None:
    ctx = TenantContext(tenant_id=TenantId("acme"), metadata={"region": "eu"})
    assert ctx.metadata == {"region": "eu"}


def test_current_tenant_raises_when_unbound() -> None:
    assert try_current_tenant() is None
    with pytest.raises(MissingTenantContextError) as exc_info:
        current_tenant()
    assert exc_info.value.operation == "current_tenant"


def test_try_current_tenant_returns_none_when_unbound() -> None:
    assert try_current_tenant() is None


def test_tenant_scope_binds_and_releases() -> None:
    ctx = bind_tenant(TenantId("acme"))
    with tenant_scope(ctx):
        assert current_tenant() is ctx
    assert try_current_tenant() is None
    with pytest.raises(MissingTenantContextError):
        current_tenant()


def test_tenant_scope_nested_inner_wins() -> None:
    outer = bind_tenant(TenantId("outer"))
    inner = bind_tenant(TenantId("inner"))
    with tenant_scope(outer):
        assert current_tenant() is outer
        with tenant_scope(inner):
            assert current_tenant() is inner
        assert current_tenant() is outer
    assert try_current_tenant() is None


def test_tenant_scope_exception_propagates_and_releases() -> None:
    ctx = bind_tenant(TenantId("acme"))

    class _BoomError(Exception):
        pass

    with pytest.raises(_BoomError), tenant_scope(ctx):
        raise _BoomError

    assert try_current_tenant() is None


def test_bind_tenant_creates_context() -> None:
    ctx = bind_tenant(TenantId("acme"), region="eu", tier="enterprise")
    assert isinstance(ctx, TenantContext)
    assert ctx.tenant_id == "acme"
    assert ctx.metadata == {"region": "eu", "tier": "enterprise"}
    # bind_tenant must NOT activate the scope automatically.
    assert try_current_tenant() is None


def test_bind_tenant_positional_only() -> None:
    with pytest.raises(TypeError):
        bind_tenant(tenant_id=TenantId("acme"))  # type: ignore[call-arg]
