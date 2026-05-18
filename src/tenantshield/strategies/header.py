"""HeaderStrategy -- extract tenant identifier from an HTTP request header."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield._types import TenantId

if TYPE_CHECKING:
    from tenantshield.strategies.base import RequestProtocol


class HeaderStrategy:
    """Extract tenant from a configurable HTTP header.

    Default header is ``X-Tenant-Id``. Header lookup is case-insensitive
    via the ``RequestProtocol.get_header`` method; adapters handle the
    framework-specific normalization (WSGI ``HTTP_*`` mangling, ASGI
    byte-string headers list).

    Example::

        strategy = HeaderStrategy(header_name="X-Tenant-Id")
        # Request with header 'X-Tenant-Id: globex' yields TenantId('globex').

    Implements ``TenantExtractionStrategy`` structurally.

    Args:
        header_name: HTTP header name in client-facing form (e.g.,
            ``X-Tenant-Id``). Defaults to ``X-Tenant-Id``.
    """

    def __init__(self, *, header_name: str = "X-Tenant-Id") -> None:
        self.header_name = header_name

    def extract(self, request: RequestProtocol) -> TenantId | None:
        """Return the header value as ``TenantId``, or ``None`` if absent."""
        value = request.get_header(self.header_name)
        if not value:
            return None
        return TenantId(value)
