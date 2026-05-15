"""TenantExtractionStrategy Protocol -- contract for tenant extraction.

All extraction strategies (Subdomain, Header, JWT, Callable) implement
this Protocol. The Protocol is runtime-checkable for ergonomics
(isinstance(obj, TenantExtractionStrategy) works in tests) but the
canonical way to declare conformance is structural typing without
explicit inheritance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tenantshield import TenantId


@runtime_checkable
class TenantExtractionStrategy(Protocol):
    """Contract for tenant extraction from a Django request.

    Implementations must not bind or scope the tenant; that is the
    middleware's responsibility. The strategy is pure: input is the
    request, output is the tenant id (or a raised
    TenantExtractionError).
    """

    def extract(self, request: HttpRequest) -> TenantId:
        """Return the tenant id for the request.

        Args:
            request: Django HttpRequest from which to extract the tenant.

        Returns:
            TenantId extracted from the request.

        Raises:
            TenantExtractionError: when the strategy cannot extract a
                tenant from the request (missing header, invalid
                subdomain pattern, malformed JWT, etc.). The middleware
                catches this and dispatches to the configured
                on_missing_tenant behavior.
        """
        ...
