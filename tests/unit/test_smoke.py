"""Smoke tests verifying the public package surface."""

from __future__ import annotations

import re

import tenantshield
from tenantshield.audit import emit as _emit


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


def test_audit_api_is_exported() -> None:
    """Audit public API is accessible from tenantshield top-level."""
    expected = {
        "AuditEvent",
        "AuditEventType",
        "AuditSink",
        "InMemorySink",
        "NullSink",
        "StructLogSink",
        "audit_emit",
        "register_sink",
        "unregister_sink",
    }
    for name in expected:
        assert name in tenantshield.__all__, f"tenantshield.__all__ missing {name}"
        assert hasattr(tenantshield, name), f"tenantshield.{name} missing"


def test_policies_api_is_exported() -> None:
    """Policies public API is accessible from tenantshield top-level."""
    expected = {
        "Allow",
        "AllowListPolicy",
        "ChainPolicy",
        "Decision",
        "Deny",
        "DenyByDefaultPolicy",
        "Operation",
        "OperationType",
        "Policy",
        "RequireScope",
        "evaluate_and_audit",
    }
    for name in expected:
        assert name in tenantshield.__all__, f"tenantshield.__all__ missing {name}"
        assert hasattr(tenantshield, name), f"tenantshield.{name} missing"


def test_emit_re_exported_as_audit_emit() -> None:
    """The `emit` function is re-exported as `audit_emit` at top level."""
    assert tenantshield.audit_emit is _emit


def test_registry_api_is_exported() -> None:
    """Registry public API is accessible from tenantshield top-level."""
    expected = {
        "ModelRegistry",
        "RegistryEntry",
        "default_registry",
        "get_tenant_field",
        "is_tenant_aware",
        "register_model",
    }
    for name in expected:
        assert name in tenantshield.__all__, f"tenantshield.__all__ missing {name}"
        assert hasattr(tenantshield, name), f"tenantshield.{name} missing"
