"""TenantExtractionStrategy Protocol -- Django adapter contract for strategies.

Phase 4B Decision 6-A: this module preserves the Phase 2B adopter
Protocol typed against ``HttpRequest`` (narrower than the cross-adapter
core Protocol typed against ``RequestProtocol``). The Django Protocol
is distinct from :class:`tenantshield.strategies.TenantExtractionStrategy`
at the type-system level; runtime conformance checks (
``isinstance(obj, ...)``) match structurally for both Protocols because
``runtime_checkable`` Protocol only verifies method names.

Strategies in this Django adapter module subclass the cross-adapter
core implementations to share extraction logic but type their ``extract``
method against ``HttpRequest`` for adopter clarity and mypy/pyright
compatibility with the Django middleware layer.
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
    TenantExtractionError per Phase 2B contract).
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
