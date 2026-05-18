"""SubdomainStrategy -- Django adapter shim over ``tenantshield.strategies.HostStrategy``.

Phase 4B Decision 5-B + 6-A: ``HostStrategy`` is the cross-adapter
canonical name; Django adopters keep the ``SubdomainStrategy`` symbol
as an alias preserving Phase 2B import paths and behavior. The Django
strategy subclasses the cross-adapter ``HostStrategy``, internally
wraps ``HttpRequest`` in ``DjangoRequestAdapter``, and translates the
core return-``None``-on-failure contract back to Phase 2B
raise-on-failure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield.adapters.django.exceptions import TenantExtractionError
from tenantshield.adapters.django.middleware.strategies._request_adapter import (
    DjangoRequestAdapter,
)
from tenantshield.strategies import HostStrategy as _CoreHostStrategy

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tenantshield._types import TenantId


class SubdomainStrategy(_CoreHostStrategy):
    """Extract tenant from the leftmost label of the request host (Phase 2B name).

    Subclass of :class:`tenantshield.strategies.HostStrategy` preserving
    the Phase 2B ``SubdomainStrategy`` adopter symbol with single-tier
    raise-on-failure semantics.

    Examples:
        - 'acme.example.com'      -> 'acme'
        - 'acme.example.com:8000' -> 'acme' (port stripped)
        - 'example.com'           -> raises TenantExtractionError
        - 'localhost'             -> raises TenantExtractionError

    Implements the TenantExtractionStrategy Protocol structurally.
    """

    def extract(self, request: HttpRequest) -> TenantId:  # type: ignore[override]
        """Return the subdomain as TenantId, or raise.

        Type narrowing vs core (``RequestProtocol`` -> ``HttpRequest``,
        ``TenantId | None`` -> ``TenantId``) is intentional per Phase 2B
        contract preservation.

        Raises:
            TenantExtractionError: when the host has fewer than three
                dot-separated labels (Phase 2B contract preservation).
        """
        adapter = DjangoRequestAdapter(request)
        result = super().extract(adapter)
        if result is None:
            host = request.get_host()
            host_no_port = host.split(":", 1)[0]
            parts = host_no_port.split(".")
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason=f"Cannot extract subdomain from host {host_no_port!r}",
                context={"host": host_no_port, "parts": parts},
            )
        return result
