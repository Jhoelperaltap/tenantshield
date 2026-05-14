"""Smoke tests verifying the public package surface."""

from __future__ import annotations

import re

import tenantshield


def test_package_imports() -> None:
    assert tenantshield is not None


def test_version_is_pep440() -> None:
    assert re.match(r"^\d+\.\d+\.\d+(a|b|rc)?\d*$", tenantshield.__version__)


def test_public_api_is_explicit() -> None:
    assert hasattr(tenantshield, "__all__")
    assert "__version__" in tenantshield.__all__


def test_context_api_is_exported() -> None:
    for name in (
        "TenantContext",
        "TenantId",
        "atenant_scope",
        "bind_tenant",
        "current_tenant",
        "tenant_scope",
        "try_current_tenant",
    ):
        assert name in tenantshield.__all__
        assert hasattr(tenantshield, name)


def test_exception_api_is_exported() -> None:
    for name in (
        "AdapterError",
        "AmbiguousTenantContextError",
        "ConfigurationError",
        "CrossTenantAccessError",
        "CrossTenantJoinError",
        "EnforcementError",
        "MissingTenantContextError",
        "TenantContextError",
        "TenantShieldError",
        "UnscopedQueryError",
    ):
        assert name in tenantshield.__all__
        assert hasattr(tenantshield, name)


def test_all_exception_classes_inherit_base() -> None:
    for name in (
        "AdapterError",
        "AmbiguousTenantContextError",
        "ConfigurationError",
        "CrossTenantAccessError",
        "CrossTenantJoinError",
        "EnforcementError",
        "MissingTenantContextError",
        "TenantContextError",
        "UnscopedQueryError",
    ):
        exc_class = getattr(tenantshield, name)
        assert issubclass(exc_class, tenantshield.TenantShieldError)
