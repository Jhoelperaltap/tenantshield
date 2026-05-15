"""URL patterns for the testapp Django app.

This module exists for integration tests of TenantContextMiddleware in
Sub-phase 2B.9. It is referenced by tests/integration/django/settings.py
via ROOT_URLCONF.
"""

from __future__ import annotations

from django.urls import path

from tests.integration.django.testapp import views

urlpatterns = [
    path("invoices/", views.invoice_list, name="invoice-list"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice-detail"),
    path("health/", views.health_check, name="health-check"),
]
