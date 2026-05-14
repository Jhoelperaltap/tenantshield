"""Tests for tenantshield.registry default_registry + convenience functions."""

from __future__ import annotations

import pytest

import tenantshield.registry as _registry_module
from tenantshield.exceptions import ConfigurationError
from tenantshield.registry import (
    default_registry,
    get_tenant_field,
    is_tenant_aware,
    register_model,
)


@pytest.fixture(autouse=True)
def _clear_default_registry() -> None:
    """Ensure each test starts and ends with the default registry empty."""
    default_registry.clear()
    yield
    default_registry.clear()


def test_default_registry_is_module_singleton() -> None:
    """The default_registry symbol is a module-level singleton."""
    assert _registry_module.default_registry is default_registry


def test_register_model_decorator_no_args() -> None:
    """@register_model (no parens) registers and returns the class."""

    @register_model
    class _Invoice:
        """Test model."""

    assert default_registry.is_registered(_Invoice)
    assert default_registry.get(_Invoice).tenant_field == "tenant_id"
    # The decorator returns the class itself, not a wrapper.
    assert _Invoice.__name__ == "_Invoice"


def test_register_model_decorator_with_args() -> None:
    """@register_model(tenant_field=...) configures the field."""

    @register_model(tenant_field="org_id")
    class _Org:
        """Test model."""

    assert default_registry.is_registered(_Org)
    assert default_registry.get(_Org).tenant_field == "org_id"


def test_register_model_direct_call() -> None:
    """register_model(Cls) registers directly with default tenant_field."""

    class _DirectA:
        """Test model."""

    result = register_model(_DirectA)
    assert result is _DirectA
    assert default_registry.is_registered(_DirectA)
    assert default_registry.get(_DirectA).tenant_field == "tenant_id"


def test_register_model_direct_call_with_kwarg() -> None:
    """register_model(Cls, tenant_field='x') registers with explicit field."""

    class _DirectB:
        """Test model."""

    result = register_model(_DirectB, tenant_field="account_id")
    assert result is _DirectB
    assert default_registry.get(_DirectB).tenant_field == "account_id"


def test_is_tenant_aware_registered() -> None:
    """is_tenant_aware returns True for registered models."""

    @register_model
    class _Reg:
        """Test model."""

    assert is_tenant_aware(_Reg) is True


def test_is_tenant_aware_unregistered() -> None:
    """is_tenant_aware returns False for unregistered models."""

    class _NotReg:
        """Test model."""

    assert is_tenant_aware(_NotReg) is False


def test_get_tenant_field_registered() -> None:
    """get_tenant_field returns the configured field."""

    @register_model(tenant_field="org_id")
    class _Reg:
        """Test model."""

    assert get_tenant_field(_Reg) == "org_id"


def test_get_tenant_field_unregistered_raises() -> None:
    """get_tenant_field raises ConfigurationError for unregistered models."""

    class _NotReg:
        """Test model."""

    with pytest.raises(ConfigurationError) as exc_info:
        get_tenant_field(_NotReg)

    assert "_NotReg" in str(exc_info.value)
