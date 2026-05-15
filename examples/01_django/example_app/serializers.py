"""DRF serializers for example_app.

Demonstrates TenantValidatedSerializerMixin usage on Invoice and Org
models. Auto-injects tenant_id from active scope on create; rejects
mismatched tenant_id on create/update with TenantPermissionDenied.

This is the canonical pattern for adopters: declare ModelSerializer
+ mix in TenantValidatedSerializerMixin first in MRO. The mixin
intercepts at to_internal_value pre-validation (auto-inject) and at
create/update post-validation (mismatch detection).
"""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from tenantshield.adapters.drf import TenantValidatedSerializerMixin

from example_app.models import Invoice, Org


class OrgSerializer(TenantValidatedSerializerMixin, serializers.ModelSerializer[Org]):
    """Org serializer with tenant validation."""

    class Meta:
        model = Org
        fields: ClassVar[list[str]] = ["id", "tenant_id", "name"]


class InvoiceSerializer(
    TenantValidatedSerializerMixin,
    serializers.ModelSerializer[Invoice],
):
    """Invoice serializer with tenant validation."""

    class Meta:
        model = Invoice
        fields: ClassVar[list[str]] = [
            "id",
            "tenant_id",
            "amount",
            "description",
            "created_at",
        ]
        read_only_fields: ClassVar[list[str]] = ["created_at"]
