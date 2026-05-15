"""DRF adapter-specific exceptions.

These are distinct from core exceptions in tenantshield.exceptions:
they are raised by the DRF layer (permission denials, serializer
validation failures) and integrate with DRF's exception handling
machinery (HTTP 403 response generation).

TenantPermissionDenied subclasses DRF's PermissionDenied so that DRF's
default exception handler translates it to HTTP 403 with the configured
detail message. The exception carries optional context for diagnostics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.exceptions import PermissionDenied

if TYPE_CHECKING:
    from collections.abc import Mapping


class TenantPermissionDenied(PermissionDenied):
    """Raised when a DRF operation violates tenant isolation.

    Subclass of DRF's PermissionDenied; DRF's default exception handler
    translates this to an HTTP 403 response automatically.

    Args:
        detail: Human-readable reason for the denial (returned in the
            HTTP response body per DRF convention).
        context: Optional context dict for structured logging.
    """

    def __init__(
        self,
        detail: str | None = None,
        context: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(detail=detail)
        self.context: Mapping[str, object] = context or {}
