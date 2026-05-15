"""Smoke test for examples/01_django runnable mini-project.

Verifies the example structure is intact via file content inspection.
Full HTTP E2E is covered by tests/integration/django/test_drf.py
(TestDRFIntegrationEndToEnd) against testapp viewsets, which mirror
the example pattern. Re-testing the same DRF enforcement here via
subprocess + HTTP would add fragility without coverage value.

These tests do NOT require installing the example -- they read files
directly. Adopters can verify their own install by following the
README walkthrough manually.
"""

from __future__ import annotations

from pathlib import Path

EXAMPLE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "examples" / "01_django"


class TestExample01DjangoStructure:
    """Verify the example mini-project structure is intact."""

    def test_example_directory_exists(self):
        assert EXAMPLE_DIR.exists()
        assert (EXAMPLE_DIR / "manage.py").is_file()
        assert (EXAMPLE_DIR / "pyproject.toml").is_file()
        assert (EXAMPLE_DIR / "README.md").is_file()
        assert (EXAMPLE_DIR / "example_project" / "settings.py").is_file()
        assert (EXAMPLE_DIR / "example_project" / "urls.py").is_file()
        assert (EXAMPLE_DIR / "example_app" / "models.py").is_file()
        assert (EXAMPLE_DIR / "example_app" / "serializers.py").is_file()
        assert (EXAMPLE_DIR / "example_app" / "viewsets.py").is_file()
        assert (EXAMPLE_DIR / "example_app" / "urls.py").is_file()

    def test_pyproject_declares_tenantshield_with_extras(self):
        content = (EXAMPLE_DIR / "pyproject.toml").read_text()
        assert "tenantshield" in content
        assert "[django,jwt,drf]" in content
        assert "djangorestframework" in content
        assert "[tool.setuptools]" in content
        assert "example_app" in content
        assert "example_project" in content

    def test_settings_installs_tenantshield_middleware(self):
        content = (EXAMPLE_DIR / "example_project" / "settings.py").read_text()
        assert "TenantContextMiddleware" in content
        assert '"header"' in content or "'header'" in content
        assert "X-Tenant-Id" in content
        assert '"raise"' in content or "'raise'" in content

    def test_models_use_tenant_aware(self):
        content = (EXAMPLE_DIR / "example_app" / "models.py").read_text()
        assert "from tenantshield.adapters.django import tenant_aware" in content
        assert "@tenant_aware" in content
        assert "class Invoice" in content
        assert "class Org" in content

    def test_serializers_use_validated_mixin(self):
        content = (EXAMPLE_DIR / "example_app" / "serializers.py").read_text()
        assert "TenantValidatedSerializerMixin" in content
        assert "InvoiceSerializer" in content
        assert "OrgSerializer" in content

    def test_viewsets_use_mixin_and_permission(self):
        content = (EXAMPLE_DIR / "example_app" / "viewsets.py").read_text()
        assert "TenantAwareViewSetMixin" in content
        assert "IsSameTenant" in content
        assert "permission_classes" in content

    def test_urls_register_viewsets(self):
        content = (EXAMPLE_DIR / "example_app" / "urls.py").read_text()
        assert "DefaultRouter" in content
        assert "InvoiceViewSet" in content
        assert "OrgViewSet" in content
        assert "invoices" in content
        assert "orgs" in content

    def test_readme_documents_walkthrough(self):
        content = (EXAMPLE_DIR / "README.md").read_text()
        assert "TenantShield Django Example" in content
        assert "X-Tenant-Id" in content
        assert "curl" in content
        assert "Common gotchas" in content
