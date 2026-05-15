"""SubdomainStrategy -- extract tenant from the request's subdomain.

For a host like 'acme.example.com' or 'acme.example.com:8000', the
tenant id is 'acme' (the leftmost label). Hosts with fewer than three
dot-separated labels (e.g., 'example.com', 'localhost') cannot yield
a subdomain and raise TenantExtractionError.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield import TenantId
from tenantshield.adapters.django.exceptions import TenantExtractionError

if TYPE_CHECKING:
    from django.http import HttpRequest

# A host yields a subdomain only when it has at least three dot-separated
# labels: <subdomain>.<domain>.<tld>. Fewer labels (e.g. 'example.com',
# 'localhost') cannot produce a tenant identifier.
_MIN_HOST_LABELS_FOR_SUBDOMAIN = 3


class SubdomainStrategy:
    """Extract tenant from the leftmost label of the request host.

    Examples:
        - 'acme.example.com'      -> 'acme'
        - 'acme.example.com:8000' -> 'acme' (port stripped)
        - 'example.com'           -> raises TenantExtractionError
        - 'localhost'             -> raises TenantExtractionError

    Implements the TenantExtractionStrategy Protocol structurally.
    """

    def extract(self, request: HttpRequest) -> TenantId:
        """Return the subdomain as TenantId, or raise.

        Raises:
            TenantExtractionError: when the host has fewer than three
                dot-separated labels.
        """
        host = request.get_host()
        host_no_port = host.split(":", 1)[0]
        parts = host_no_port.split(".")
        if len(parts) < _MIN_HOST_LABELS_FOR_SUBDOMAIN:
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason=f"Cannot extract subdomain from host {host_no_port!r}",
                context={"host": host_no_port, "parts": parts},
            )
        return TenantId(parts[0])
