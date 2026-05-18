"""HostStrategy -- extract tenant identifier from the request host's subdomain.

Replaces Django-specific ``SubdomainStrategy`` with framework-agnostic
implementation operating on ``RequestProtocol.get_host()`` (Decision 5-B
from the Phase 4 kickoff).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield._types import TenantId

if TYPE_CHECKING:
    from tenantshield.strategies.base import RequestProtocol


# A host yields a subdomain only when it has at least three dot-separated
# labels: <subdomain>.<domain>.<tld>. Fewer labels (e.g., "example.com",
# "localhost") cannot produce a tenant identifier.
_MIN_HOST_LABELS_FOR_SUBDOMAIN = 3


class HostStrategy:
    """Extract tenant from the leftmost subdomain segment of the request host.

    Examples:

    - ``"acme.example.com"`` -> ``TenantId("acme")``.
    - ``"acme.example.com:8000"`` -> ``TenantId("acme")`` (port stripped).
    - ``"team.acme.example.com"`` -> ``TenantId("team")`` (leftmost label).
    - ``"example.com"`` -> ``None`` (no subdomain segment).
    - ``"localhost"`` -> ``None``.
    - ``""`` -> ``None``.

    Cross-adapter equivalent of Phase 2B ``SubdomainStrategy``. The
    parsing logic (port strip, leftmost-label extraction, three-label
    minimum) follows HTTP host syntax and is not Django-specific.

    Implements ``TenantExtractionStrategy`` structurally.
    """

    def extract(self, request: RequestProtocol) -> TenantId | None:
        """Return the leftmost subdomain as ``TenantId``, or ``None``."""
        host = request.get_host()
        if not host:
            return None
        host_no_port = host.split(":", 1)[0]
        parts = host_no_port.split(".")
        if len(parts) < _MIN_HOST_LABELS_FOR_SUBDOMAIN:
            return None
        return TenantId(parts[0])
