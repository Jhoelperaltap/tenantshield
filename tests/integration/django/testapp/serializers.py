"""DRF serializers for testapp models, consuming TenantShield mixins.

Used by tests/integration/django/test_drf.py End-to-End class
(2C.A.5) and serves as canonical example of mixin usage in tests.
"""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from tenantshield.adapters.drf import TenantValidatedSerializerMixin
from tests.integration.django.testapp.models import Invoice


class InvoiceSerializer(
    TenantValidatedSerializerMixin,
    serializers.ModelSerializer[Invoice],
):
    """Invoice serializer with tenant validation."""

    class Meta:
        model = Invoice
        fields: ClassVar[list[str]] = ["id", "tenant_id", "amount", "description"]
