"""pytest-django configuration and fixtures for integration tests."""

from __future__ import annotations

import os

import django
import pytest
from django.conf import settings

from tenantshield import TenantId, bind_tenant, tenant_scope


def pytest_configure(config: object) -> None:  # noqa: ARG001
    """Configure Django before tests run."""
    if not settings.configured:
        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE",
            "tests.integration.django.settings",
        )
        django.setup()


@pytest.fixture
def tenant_acme():
    return bind_tenant(TenantId("acme"))


@pytest.fixture
def tenant_globex():
    return bind_tenant(TenantId("globex"))


@pytest.fixture
def invoices(db, tenant_acme, tenant_globex):  # noqa: ARG001
    """Seed invoices across two tenants.

    Uses ``tenant_scope`` for each tenant rather than ``_unscoped`` because
    the pre_save signal is connected to the model class (not the manager),
    so ``_unscoped`` bypasses manager filtering but does not bypass the
    write-path validation in signals. Seeding through ``tenant_scope`` is
    the correct, contract-aligned path.
    """
    # Import deferred until Django is configured by pytest_configure.
    from tests.integration.django.testapp.models import Invoice  # noqa: PLC0415

    with tenant_scope(tenant_acme):
        Invoice.objects.create(tenant_id="acme", amount=100, description="acme-1")
        Invoice.objects.create(tenant_id="acme", amount=200, description="acme-2")

    with tenant_scope(tenant_globex):
        Invoice.objects.create(tenant_id="globex", amount=300, description="globex-1")
