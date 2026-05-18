"""JWTStrategy -- Django adapter shim over ``tenantshield.strategies.JWTStrategy``.

Phase 4B Decision 6-A: refactor in-place, preserve Phase 2B contract.
The Django strategy subclasses the cross-adapter core JWTStrategy,
internally wraps ``HttpRequest`` in ``DjangoRequestAdapter``, and
translates:

- Core returns ``None`` when Authorization header missing or not Bearer
  -> Django shim raises ``TenantExtractionError`` (Phase 2B contract).
- Core raises ``tenantshield.strategies.TenantExtractionError`` on
  decode failure or missing claim -> Django shim re-raises the
  Django-namespaced ``TenantExtractionError`` (with ``from exc``
  preserving the cause chain).

Requires PyJWT (optional ``[jwt]`` extra). The import is performed by
the core class at construction time; the Django subclass surfaces the
same ``ImportError`` semantics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield.adapters.django.exceptions import TenantExtractionError
from tenantshield.adapters.django.middleware.strategies._request_adapter import (
    DjangoRequestAdapter,
)
from tenantshield.strategies import JWTStrategy as _CoreJWTStrategy
from tenantshield.strategies import TenantExtractionError as _CoreTenantExtractionError

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tenantshield._types import TenantId


class JWTStrategy(_CoreJWTStrategy):
    """Extract tenant from a JWT in the Authorization header (Phase 2B contract).

    Subclass of :class:`tenantshield.strategies.JWTStrategy` preserving
    the Phase 2B Django contract: all failure modes raise
    ``TenantExtractionError`` from ``tenantshield.adapters.django.exceptions``.

    Example:
        strategy = JWTStrategy(secret="my-secret", claim="tenant_id")
        # Request with header "Authorization: Bearer <token>" where the
        # token's payload contains {"tenant_id": "umbrella"} returns
        # TenantId("umbrella") from extract().

    Implements the TenantExtractionStrategy Protocol structurally.
    """

    def __init__(
        self,
        secret: str,
        claim: str = "tenant_id",
        algorithm: str = "HS256",
    ) -> None:
        """Initialize with JWT decode parameters (Phase 2B positional signature).

        Args:
            secret: Secret key for JWT signature verification.
            claim: Name of the JWT claim carrying the tenant id.
            algorithm: JWT signing algorithm.

        Raises:
            ImportError: when PyJWT is not installed. Install via the
                optional extra: ``pip install 'tenantshield[jwt]'``.
        """
        super().__init__(secret=secret, claim=claim, algorithm=algorithm)

    def extract(self, request: HttpRequest) -> TenantId:  # type: ignore[override]
        """Decode the Bearer token and return the claim as TenantId.

        Type narrowing vs core is intentional per Phase 2B contract
        preservation (all failure modes raise; core returns ``None`` on
        missing Authorization header).

        Raises:
            TenantExtractionError: when the Authorization header is
                missing, not in Bearer format, decoding fails, or the
                target claim is missing/empty (Phase 2B contract).
        """
        adapter = DjangoRequestAdapter(request)
        try:
            result = super().extract(adapter)
        except _CoreTenantExtractionError as exc:
            # Translate core extraction error to the Django adapter
            # namespaced error for Phase 2B contract preservation.
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason=exc.reason,
                context=exc.context,
            ) from exc

        if result is None:
            # Core returned None: Authorization header missing or not Bearer.
            # Phase 2B contract requires raising.
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason="Authorization header missing or not Bearer",
                context={"auth_header_present": bool(adapter.get_header("Authorization"))},
            )
        return result
