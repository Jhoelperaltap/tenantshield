"""DRF viewsets for example_app.

Demonstrates the full DR-019 triple defense:
1. permission_classes = [IsSameTenant]: request/object level.
2. TenantAwareViewSetMixin: queryset filtering at construction.
3. TenantValidatedSerializerMixin (via serializer_class): write-path
   validation.

Pattern A (Model.objects.all() via get_queryset override): the
@tenant_aware manager filters, the mixin acts as guard but does
not engage.
"""

from __future__ import annotations

from rest_framework.viewsets import ModelViewSet

from tenantshield.adapters.drf import IsSameTenant, TenantAwareViewSetMixin

from example_app.models import Invoice, Org
from example_app.serializers import InvoiceSerializer, OrgSerializer


class OrgViewSet(TenantAwareViewSetMixin, ModelViewSet[Org]):
    """Org CRUD endpoints, multi-tenant isolated."""

    serializer_class = OrgSerializer
    permission_classes = (IsSameTenant,)

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return Org.objects.all()


class InvoiceViewSet(TenantAwareViewSetMixin, ModelViewSet[Invoice]):
    """Invoice CRUD endpoints, multi-tenant isolated."""

    serializer_class = InvoiceSerializer
    permission_classes = (IsSameTenant,)

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return Invoice.objects.all()
