"""Tests for TenantShield system checks related to middleware misconfiguration.

Covers:
- check_middleware_strategy_configured (E002)
- check_public_tenant_mode_visible (W001)
- check_middleware_installed_for_tenant_aware_models (W002)
"""

from __future__ import annotations

from django.test import override_settings

from tenantshield.adapters.django.checks import (
    check_middleware_installed_for_tenant_aware_models,
    check_middleware_strategy_configured,
    check_public_tenant_mode_visible,
)

_MIDDLEWARE_PATH_SHORT = "tenantshield.adapters.django.TenantContextMiddleware"
_MIDDLEWARE_PATH_FULL = "tenantshield.adapters.django.middleware.TenantContextMiddleware"


# === E002 - check_middleware_strategy_configured ===


class TestCheckE002:
    """Tests for tenantshield.E002 system check."""

    @override_settings(MIDDLEWARE=[], TENANTSHIELD={})
    def test_passes_when_middleware_absent(self):
        """E002 does not trigger when middleware is not installed."""
        assert check_middleware_strategy_configured() == []

    @override_settings(
        MIDDLEWARE=[_MIDDLEWARE_PATH_SHORT],
        TENANTSHIELD={},
    )
    def test_raises_e002_when_strategy_missing(self):
        """E002 triggers when middleware installed but strategy not configured."""
        errors = check_middleware_strategy_configured()
        assert len(errors) == 1
        assert errors[0].id == "tenantshield.E002"
        assert "tenant_extraction" in errors[0].msg

    @override_settings(
        MIDDLEWARE=[_MIDDLEWARE_PATH_FULL],
        TENANTSHIELD={},
    )
    def test_detects_middleware_via_full_path(self):
        """E002 detects middleware via both short and full path."""
        errors = check_middleware_strategy_configured()
        assert len(errors) == 1
        assert errors[0].id == "tenantshield.E002"

    @override_settings(
        MIDDLEWARE=[_MIDDLEWARE_PATH_SHORT],
        TENANTSHIELD={"tenant_extraction": "subdomain"},
    )
    def test_passes_when_strategy_configured(self):
        """E002 does not trigger when strategy is properly configured."""
        assert check_middleware_strategy_configured() == []

    @override_settings(
        MIDDLEWARE=[_MIDDLEWARE_PATH_SHORT],
        TENANTSHIELD="not a dict",
    )
    def test_raises_e002_when_settings_not_dict(self):
        """E002 triggers when TENANTSHIELD is not a Mapping."""
        errors = check_middleware_strategy_configured()
        assert len(errors) == 1
        assert errors[0].id == "tenantshield.E002"
        assert "dict" in errors[0].msg.lower()


# === W001 - check_public_tenant_mode_visible ===


class TestCheckW001:
    """Tests for tenantshield.W001 system check."""

    @override_settings(
        TENANTSHIELD={
            "tenant_extraction": "subdomain",
            "on_missing_tenant": "raise",
        },
    )
    def test_passes_when_on_missing_is_raise(self):
        """W001 does not trigger when on_missing_tenant is 'raise'."""
        assert check_public_tenant_mode_visible() == []

    @override_settings(
        TENANTSHIELD={
            "tenant_extraction": "subdomain",
            "on_missing_tenant": "public",
        },
    )
    def test_warns_w001_when_on_missing_is_public(self):
        """W001 triggers when on_missing_tenant is 'public'."""
        warnings = check_public_tenant_mode_visible()
        assert len(warnings) == 1
        assert warnings[0].id == "tenantshield.W001"
        assert "public" in warnings[0].msg.lower()

    @override_settings(TENANTSHIELD="not a dict")
    def test_passes_silently_when_settings_not_dict(self):
        """W001 returns no warnings when TENANTSHIELD is not a dict.

        The E002 check handles the non-dict case with an error; W001
        intentionally bypasses to avoid duplicating the diagnostic.
        """
        assert check_public_tenant_mode_visible() == []


# === W002 - check_middleware_installed_for_tenant_aware_models ===


class TestCheckW002:
    """Tests for tenantshield.W002 system check."""

    @override_settings(MIDDLEWARE=[])
    def test_warns_w002_when_models_exist_but_middleware_absent(self):
        """W002 triggers when registered models exist and middleware is absent.

        The testapp registers Invoice and Org via @tenant_aware, so
        default_registry is non-empty in the test environment.
        """
        warnings = check_middleware_installed_for_tenant_aware_models()
        assert len(warnings) == 1
        assert warnings[0].id == "tenantshield.W002"
        assert "@tenant_aware" in warnings[0].msg

    @override_settings(MIDDLEWARE=[_MIDDLEWARE_PATH_SHORT])
    def test_passes_when_middleware_installed(self):
        """W002 does not trigger when middleware is in MIDDLEWARE."""
        assert check_middleware_installed_for_tenant_aware_models() == []

    @override_settings(MIDDLEWARE=[_MIDDLEWARE_PATH_FULL])
    def test_detects_middleware_via_full_path(self):
        """W002 detects middleware via full path as well."""
        assert check_middleware_installed_for_tenant_aware_models() == []

    def test_passes_when_no_models_registered(self, monkeypatch):
        """W002 returns no warnings when no tenant-aware models are registered.

        Patches the registry referenced by the check module to an empty
        iterable so the early-return path is exercised. Restoration is
        automatic via pytest monkeypatch teardown.
        """
        monkeypatch.setattr(
            "tenantshield.adapters.django.checks.default_registry",
            [],
        )
        assert check_middleware_installed_for_tenant_aware_models() == []
