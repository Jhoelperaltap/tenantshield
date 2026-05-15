"""URL routing for testapp -- plain Django views + DRF router.

Plain views (Sub-phase 2B middleware integration tests):
- /invoices/ -> views.invoice_list
- /invoices/<pk>/ -> views.invoice_detail
- /health/ -> views.health_check

DRF router (Sub-phase 2C E2E integration tests):
- /api/invoices/ -> InvoiceViewSet (list, create)
- /api/invoices/<pk>/ -> InvoiceViewSet (retrieve, update, destroy)
"""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tests.integration.django.testapp import views
from tests.integration.django.testapp.viewsets import InvoiceViewSet

router = DefaultRouter()
router.register(r"invoices", InvoiceViewSet, basename="invoice")

urlpatterns = [
    # Plain Django views (Sub-phase 2B middleware integration tests)
    path("invoices/", views.invoice_list, name="invoice-list"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice-detail"),
    path("health/", views.health_check, name="health-check"),
    # DRF router (Sub-phase 2C E2E integration tests)
    path("api/", include(router.urls)),
]
