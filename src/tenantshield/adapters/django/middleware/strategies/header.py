"""HeaderStrategy -- Django adapter shim over ``tenantshield.strategies.HeaderStrategy``.

Phase 4B Decision 6-A: refactor in-place, preserve Phase 2B adopter
import paths and behavior. The Django strategy subclasses the
cross-adapter core strategy, internally wraps the ``HttpRequest`` in
``DjangoRequestAdapter``, and translates the core's two-tier contract
(return ``None`` for missing) back to the Phase 2B single-tier contract
(raise ``TenantExtractionError`` on missing).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield.adapters.django.exceptions import TenantExtractionError
from tenantshield.adapters.django.middleware.strategies._request_adapter import (
    DjangoRequestAdapter,
)
from tenantshield.strategies import HeaderStrategy as _CoreHeaderStrategy

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tenantshield._types import TenantId


class HeaderStrategy(_CoreHeaderStrategy):
    """Extract tenant from an HTTP request header (Django Phase 2B contract).

    Subclass of :class:`tenantshield.strategies.HeaderStrategy` that
    preserves the Phase 2B Django contract: raises
    ``TenantExtractionError`` when the header is missing or empty
    (the core class returns ``None`` for the same condition).

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
                internally by ``DjangoRequestAdapter``.
        """
        super().__init__(header_name=header_name)
        # Phase 2B exposed ``_meta_key`` attribute publicly via tests; preserve
        # for backward compatibility even though the lookup happens via
        # ``DjangoRequestAdapter.get_header`` in the refactored code path.
        self._meta_key = "HTTP_" + header_name.upper().replace("-", "_")

    def extract(self, request: HttpRequest) -> TenantId:  # type: ignore[override]
        """Return the header value as TenantId, or raise.

        Type narrowing vs core (``RequestProtocol`` -> ``HttpRequest``,
        ``TenantId | None`` -> ``TenantId``) is intentional per Phase 2B
        contract preservation; the override translates the core's
        return-``None`` to the Django adapter raise-on-missing contract.

        Raises:
            TenantExtractionError: when the header is missing or empty
                (Phase 2B contract preservation).
        """
        adapter = DjangoRequestAdapter(request)
        result = super().extract(adapter)
        if result is None:
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason=f"Header {self.header_name!r} missing or empty",
                context={
                    "header_name": self.header_name,
                    "meta_key": self._meta_key,
                },
            )
        return result
