"""TenantContextMiddleware -- bind tenant context for the request lifecycle.

This module hosts the Django middleware that extracts the tenant from
the incoming request (via a configured TenantExtractionStrategy),
binds it via tenantshield.bind_tenant, and enters tenant_scope() for
the duration of get_response(request). After the response is generated,
the scope exits automatically (context manager semantics), ensuring
the tenant context does not leak between requests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseNotFound

from tenantshield import TenantId, bind_tenant, tenant_scope
from tenantshield.adapters.django.exceptions import TenantExtractionError
from tenantshield.adapters.django.middleware.strategies import resolve_strategy
from tenantshield.exceptions import MissingTenantContextError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from django.http import HttpRequest, HttpResponse

    from tenantshield.adapters.django.middleware.strategies import (
        TenantExtractionStrategy,
    )


_PUBLIC_TENANT = TenantId("__public__")
"""Reserved TenantId used when on_missing_tenant='public' bypasses extraction.

This value is intentionally namespaced with leading and trailing double
underscores to avoid colliding with real tenant ids. Operators should
never name a tenant '__public__' in their data.
"""


__all__ = [
    "TenantContextMiddleware",
]


class TenantContextMiddleware:
    """Django middleware that extracts tenant and enters tenant_scope.

    Per Django's middleware contract:
        __init__(get_response): called once at process startup.
        __call__(request): called per request; returns the response.

    Configuration is read from Django settings.TENANTSHIELD (a dict).
    Required key: 'tenant_extraction'. Optional key: 'on_missing_tenant'
    (default 'raise'). See DR-016 and DR-017 for design rationale.

    Example settings:
        TENANTSHIELD = {
            "tenant_extraction": "subdomain",
            "on_missing_tenant": "raise",
        }

    Raises (during __init__):
        ImproperlyConfigured: when TENANTSHIELD is missing or
            tenant_extraction is not configured. System check
            tenantshield.E002 surfaces this earlier at python manage.py
            check time.
    """

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse],
    ) -> None:
        """Load strategy + on_missing config from Django settings.

        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response
        config: Mapping[str, object] = cast(
            "Mapping[str, object]",
            getattr(settings, "TENANTSHIELD", {}),
        )
        self.strategy: TenantExtractionStrategy = resolve_strategy(config)
        self.on_missing: object = config.get("on_missing_tenant", "raise")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Extract tenant, enter scope, delegate, exit scope.

        Per-request:
            1. Invoke the configured strategy to extract tenant_id.
            2. On extraction failure, dispatch to on_missing_tenant.
            3. On success, bind_tenant + tenant_scope wrap get_response.
        """
        try:
            tenant_id = self.strategy.extract(request)
        except TenantExtractionError as exc:
            response = self._handle_missing(request, exc)
            if response is not None:
                return response
            # on_missing == "raise" path: translate to core exception.
            raise MissingTenantContextError(
                operation="middleware.extract",
                stack_context={
                    "strategy": exc.strategy_name,
                    "reason": exc.reason,
                    **dict(exc.context),
                },
            ) from exc

        ctx = bind_tenant(tenant_id)
        with tenant_scope(ctx):
            return self.get_response(request)

    def _handle_missing(
        self,
        request: HttpRequest,
        exc: TenantExtractionError,
    ) -> HttpResponse | None:
        """Dispatch to the configured on_missing_tenant behavior.

        Returns:
            HttpResponse when the behavior produces a response (404,
            public mode response, or callable returning HttpResponse).
            None when the behavior is 'raise' (caller re-raises) or
            when a callable returns None (caller re-raises).
        """
        if self.on_missing == "raise":
            return None  # caller re-raises as MissingTenantContextError

        if self.on_missing == "404":
            return HttpResponseNotFound("Tenant not found")

        if self.on_missing == "public":
            # Bind a reserved public tenant and proceed. Logged via the
            # audit bus when the integration in Phase 8 documentation
            # surfaces it. For now, the bind itself is sufficient.
            ctx = bind_tenant(_PUBLIC_TENANT)
            with tenant_scope(ctx):
                return self.get_response(request)

        if callable(self.on_missing):
            handler = cast(
                "Callable[[HttpRequest, TenantExtractionError], HttpResponse | None]",
                self.on_missing,
            )
            return handler(request, exc)

        msg = (
            f"Invalid TENANTSHIELD['on_missing_tenant']: {self.on_missing!r}. "
            "Expected 'raise', '404', 'public', or a callable."
        )
        raise ImproperlyConfigured(msg)
