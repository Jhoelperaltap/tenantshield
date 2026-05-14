"""Test models for TenantShield integration tests."""

from __future__ import annotations

from django.db import models

from tenantshield.adapters.django import tenant_aware


@tenant_aware
class Invoice(models.Model):
    """Invoice -- basic tenant-aware model with default tenant_field."""

    tenant_id = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = "testapp"


@tenant_aware(tenant_field="org_id")
class Org(models.Model):
    """Org -- tenant-aware model with custom tenant_field."""

    org_id = models.CharField(max_length=64)
    name = models.CharField(max_length=255)

    class Meta:
        app_label = "testapp"


class PlainModel(models.Model):
    """PlainModel -- NOT tenant-aware. Used to verify @tenant_aware is opt-in."""

    name = models.CharField(max_length=255)

    class Meta:
        app_label = "testapp"


class ExistingCustomManager(models.Manager):
    """Custom manager used to test @tenant_aware rejection of pre-existing managers."""


class ModelWithCustomManagerForTest(models.Model):
    """Model with a custom manager, deliberately NOT decorated with @tenant_aware.

    Used by tests that verify the decorator detects pre-existing custom
    managers and raises ``ConfigurationError`` instead of silently overwriting
    them. The explicit ``objects`` declaration prevents Django from
    auto-creating a plain Manager, so ``cls._meta.local_managers`` contains
    only the custom one.
    """

    name = models.CharField(max_length=255)
    objects = ExistingCustomManager()

    class Meta:
        app_label = "testapp"
