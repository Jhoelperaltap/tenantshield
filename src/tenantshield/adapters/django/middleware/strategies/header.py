"""HeaderStrategy -- extract tenant from an HTTP header.

Django normalizes HTTP headers in WSGI: 'X-Tenant-Id' becomes
META['HTTP_X_TENANT_ID']. This strategy reads that META key and
returns its value as the tenant id, or raises if missing/empty.

The header name is configurable at strategy construction. Default is
'X-Tenant-Id' (PascalCase form used in client code; Django normalizes
internally).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield import TenantId
from tenantshield.adapters.django.exceptions import TenantExtractionError

if TYPE_CHECKING:
    from django.http import HttpRequest


class HeaderStrategy:
    """Extract tenant from an HTTP request header.

    Example:
        strategy = HeaderStrategy(header_name="X-Tenant-Id")
        # request with header 'X-Tenant-Id: globex'
        # strategy.extract(request) returns TenantId('globex')

    Implements the TenantExtractionStrategy Protocol structurally.
    """

    def __init__(self, header_name: str = "X-Tenant-Id") -> None:
        """Initialize with the header name to extract.

        Args:
            header_name: HTTP header name in client-facing form (e.g.,
                'X-Tenant-Id'). Django's META normalization is handled
                internally (the name is converted to 'HTTP_X_TENANT_ID').
        """
        self.header_name = header_name
        self._meta_key = "HTTP_" + header_name.upper().replace("-", "_")

    def extract(self, request: HttpRequest) -> TenantId:
        """Return the header value as TenantId, or raise.

        Raises:
            TenantExtractionError: when the header is missing or empty.
        """
        value = request.META.get(self._meta_key)
        if not value:
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason=f"Header {self.header_name!r} missing or empty",
                context={
                    "header_name": self.header_name,
                    "meta_key": self._meta_key,
                },
            )
        return TenantId(value)
