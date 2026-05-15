"""Models for the TenantShield example.

Demonstrates @tenant_aware decorator usage on a simple Invoice model
+ optional Org model showing related-by-tenant entities.
"""

from __future__ import annotations

from typing import ClassVar

from django.db import models

from tenantshield.adapters.django import tenant_aware


@tenant_aware
class Org(models.Model):
    """Organization model -- represents a tenant entity."""

    tenant_id = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=255)

    class Meta:
        app_label = "example_app"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["tenant_id", "name"],
                name="unique_org_name_per_tenant",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.tenant_id})"


@tenant_aware
class Invoice(models.Model):
    """Invoice model -- multi-tenant isolated entity."""

    tenant_id = models.CharField(max_length=64, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "example_app"
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        return f"Invoice #{self.pk}: {self.description} ({self.amount})"
