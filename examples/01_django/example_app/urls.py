"""URL routing for example_app.

Exposes:
- /api/invoices/        -> InvoiceViewSet (list, create)
- /api/invoices/<pk>/   -> InvoiceViewSet (retrieve, update, destroy)
- /api/orgs/            -> OrgViewSet (list, create)
- /api/orgs/<pk>/       -> OrgViewSet (retrieve, update, destroy)

The /api/ prefix comes from
example_project/urls.py:include('example_app.urls').
"""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from example_app.viewsets import InvoiceViewSet, OrgViewSet

router = DefaultRouter()
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"orgs", OrgViewSet, basename="org")

urlpatterns = router.urls
