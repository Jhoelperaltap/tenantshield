"""Tests for @tenant_aware decorator."""

from __future__ import annotations

import pytest
from django.db import models

from tenantshield.adapters.django import tenant_aware
from tenantshield.adapters.django.managers import TenantAwareManager
from tenantshield.exceptions import ConfigurationError
from tenantshield.registry import default_registry
from tests.integration.django.testapp.models import (
    Invoice,
    ModelWithCustomManagerForTest,
    Org,
)


def test_decorator_registers_in_registry() -> None:
    """Invoice (decorated) is in default_registry with default tenant_field."""
    assert default_registry.is_registered(Invoice)
    entry = default_registry.get(Invoice)
    assert entry.tenant_field == "tenant_id"


def test_decorator_with_custom_field_registers_correctly() -> None:
    """Org (decorated with tenant_field='org_id') has the custom field."""
    assert default_registry.is_registered(Org)
    entry = default_registry.get(Org)
    assert entry.tenant_field == "org_id"


def test_decorator_installs_tenantaware_manager() -> None:
    """Invoice.objects is a TenantAwareManager instance."""
    assert isinstance(Invoice.objects, TenantAwareManager)


def test_decorator_installs_unscoped_escape_hatch() -> None:
    """Invoice._unscoped is installed and is a plain Django Manager."""
    assert hasattr(Invoice, "_unscoped")
    # _unscoped is the documented escape-hatch manager API.
    assert isinstance(Invoice._unscoped, models.Manager)  # noqa: SLF001
    assert not isinstance(Invoice._unscoped, TenantAwareManager)  # noqa: SLF001


def test_decorator_rejects_manager_class_parameter() -> None:
    """manager_class= parameter raises NotImplementedError in Sub-phase 2A."""
    with pytest.raises(NotImplementedError, match="manager_class"):

        @tenant_aware(manager_class=models.Manager)
        class _FailingModel:
            """Plain class used as test bait; never decorated successfully."""


def test_decorator_rejects_pre_existing_custom_manager() -> None:
    """Decorating a model with a custom manager raises ConfigurationError."""
    with pytest.raises(ConfigurationError, match="custom manager"):
        tenant_aware(ModelWithCustomManagerForTest)
