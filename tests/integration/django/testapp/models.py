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
