"""JWTStrategy -- decode tenant id from a JWT Bearer token.

This strategy requires PyJWT (optional extra [jwt] in pyproject.toml).
The import happens at construction time (fail-fast) so users without
the optional dependency installed get an actionable ImportError when
they try to instantiate the strategy, rather than a confusing failure
on the first request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield import TenantId
from tenantshield.adapters.django.exceptions import TenantExtractionError

if TYPE_CHECKING:
    from django.http import HttpRequest


_BEARER_PREFIX = "Bearer "


class JWTStrategy:
    """Extract tenant from a JWT in the Authorization header.

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
        """Initialize with JWT decode parameters.

        Args:
            secret: Secret key for JWT signature verification.
            claim: Name of the JWT claim carrying the tenant id.
                Defaults to ``tenant_id``.
            algorithm: JWT signing algorithm. Defaults to ``HS256``.

        Raises:
            ImportError: when PyJWT is not installed. Install via the
                optional extra: ``pip install 'tenantshield[jwt]'``.
        """
        try:
            import jwt  # noqa: PLC0415 -- optional dep, fail-fast at construction
        except ImportError as exc:
            msg = (
                "JWTStrategy requires PyJWT. Install the optional [jwt] "
                "extra: pip install 'tenantshield[jwt]'."
            )
            raise ImportError(msg) from exc

        # _jwt holds the dynamically imported module; django-stubs cannot
        # follow this for typing, so member access is annotated as needed.
        self._jwt = jwt
        self.secret = secret
        self.claim = claim
        self.algorithm = algorithm

    def extract(self, request: HttpRequest) -> TenantId:
        """Decode the Bearer token and return the claim as TenantId.

        Raises:
            TenantExtractionError: when the Authorization header is
                missing, not in Bearer format, decoding fails (invalid
                signature, expired, malformed), or the target claim is
                missing/empty.
        """
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith(_BEARER_PREFIX):
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason="Authorization header missing or not Bearer",
                context={"auth_header_present": bool(auth)},
            )
        token = auth.removeprefix(_BEARER_PREFIX).strip()
        try:
            payload = self._jwt.decode(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                token,
                self.secret,
                algorithms=[self.algorithm],
            )
        except self._jwt.PyJWTError as exc:  # pyright: ignore[reportUnknownMemberType, reportGeneralTypeIssues]
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason=f"JWT decode failed: {exc}",
                context={"claim": self.claim, "algorithm": self.algorithm},
            ) from exc

        tenant = payload.get(self.claim)
        if not tenant:
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason=f"JWT claim {self.claim!r} missing or empty",
                context={"claim": self.claim},
            )
        return TenantId(str(tenant))
