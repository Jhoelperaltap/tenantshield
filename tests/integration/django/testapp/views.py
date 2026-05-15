"""Views for integration tests of TenantContextMiddleware.

These views exercise the middleware lifecycle end-to-end:
- invoice_list returns the count of invoices visible to the current
  tenant (or 'no-tenant' if no scope is active).
- invoice_detail returns one invoice or 404.
- health_check returns 'ok' regardless of tenant context (useful for
  testing on_missing_tenant configurations).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import HttpResponse, JsonResponse

from tenantshield import try_current_tenant

if TYPE_CHECKING:
    from django.http import HttpRequest


def invoice_list(request: HttpRequest) -> JsonResponse:  # noqa: ARG001 -- Django view contract requires request as first arg
    """Return invoice count for the active tenant.

    Imports Invoice locally to avoid Django app-loading issues at
    module import time.
    """
    from tests.integration.django.testapp.models import Invoice  # noqa: PLC0415

    ctx = try_current_tenant()
    if ctx is None:
        return JsonResponse(
            {"tenant": None, "count": 0, "message": "no tenant scope"},
        )

    count = Invoice.objects.count()
    return JsonResponse({"tenant": ctx.tenant_id, "count": count})


def invoice_detail(request: HttpRequest, pk: int) -> JsonResponse:  # noqa: ARG001 -- Django view contract requires request as first arg
    """Return a single invoice or raise DoesNotExist (Django translates to 404)."""
    from tests.integration.django.testapp.models import Invoice  # noqa: PLC0415

    invoice = Invoice.objects.get(pk=pk)
    return JsonResponse(
        {
            "pk": invoice.pk,
            "tenant_id": invoice.tenant_id,
            "amount": str(invoice.amount),
        },
    )


def health_check(request: HttpRequest) -> HttpResponse:  # noqa: ARG001 -- Django view contract requires request as first arg
    """Health check endpoint that does not depend on tenant context.

    Useful for verifying on_missing_tenant='404' returns 404 for normal
    routes while public endpoints like /health/ remain reachable -- but
    note that this view does NOT bypass the middleware. To make /health/
    bypass tenant extraction, you would need a per-route exemption,
    deferred to a later phase.
    """
    return HttpResponse("ok", content_type="text/plain")
