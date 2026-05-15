"""DRF viewsets for testapp models, consuming TenantShield mixins.

Used by tests/integration/django/test_drf.py End-to-End class
(2C.A.5) and serves as canonical example of mixin usage in tests.
"""

from __future__ import annotations

from rest_framework.viewsets import ModelViewSet

from tenantshield.adapters.drf import IsSameTenant, TenantAwareViewSetMixin
from tests.integration.django.testapp.models import Invoice
from tests.integration.django.testapp.serializers import InvoiceSerializer


class InvoiceViewSet(TenantAwareViewSetMixin, ModelViewSet[Invoice]):
    """Invoice ViewSet with tenant filtering + IsSameTenant permission.

    Uses Pattern A (Model.objects.all() via get_queryset override):
    manager filters by tenant, mixin idle but present as guard.
    """

    serializer_class = InvoiceSerializer
    permission_classes = (IsSameTenant,)

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return Invoice.objects.all()
