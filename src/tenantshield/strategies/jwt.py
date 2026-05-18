"""JWTStrategy -- decode tenant identifier from a JWT Bearer token.

Requires PyJWT (optional ``[jwt]`` extra in ``pyproject.toml``). The
import happens at construction time (fail-fast) so adopters without
the optional dependency get an actionable ``ImportError`` when
instantiating the strategy, not on the first request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield._types import TenantId
from tenantshield.strategies.base import TenantExtractionError

if TYPE_CHECKING:
    from tenantshield.strategies.base import RequestProtocol


_BEARER_PREFIX = "Bearer "


class JWTStrategy:
    """Extract tenant from a JWT in the ``Authorization`` header.

    Contract:

    - Missing ``Authorization`` header or non-Bearer scheme: returns
      ``None`` (strategy does not apply; fall-through to middleware
      ``on_missing_tenant`` behavior).
    - Bearer token present but decode fails (invalid signature,
      expired, malformed): raises ``TenantExtractionError``.
    - Claim missing or empty after successful decode: raises
      ``TenantExtractionError``.

    Example::

        strategy = JWTStrategy(secret="...", claim="tenant_id")
        # Request with header "Authorization: Bearer <token>" whose
        # payload contains {"tenant_id": "umbrella"} returns
        # TenantId("umbrella").

    Implements ``TenantExtractionStrategy`` structurally.

    Args:
        secret: Secret key for JWT signature verification.
        claim: Name of the JWT claim carrying the tenant id. Defaults
            to ``tenant_id``.
        algorithm: JWT signing algorithm. Defaults to ``HS256``.

    Raises:
        ImportError: when PyJWT is not installed. Install the optional
            extra: ``pip install 'tenantshield[jwt]'``.
    """

    def __init__(
        self,
        *,
        secret: str,
        claim: str = "tenant_id",
        algorithm: str = "HS256",
    ) -> None:
        try:
            import jwt  # noqa: PLC0415 -- optional dep, fail-fast at construction
        except ImportError as exc:
            msg = (
                "JWTStrategy requires PyJWT. Install the optional [jwt] "
                "extra: pip install 'tenantshield[jwt]'."
            )
            raise ImportError(msg) from exc

        # ``_jwt`` holds the dynamically imported module; type stubs
        # cannot follow this attribute reliably (paralelo Phase 2B
        # precedent).
        self._jwt = jwt
        self.secret = secret
        self.claim = claim
        self.algorithm = algorithm

    def extract(self, request: RequestProtocol) -> TenantId | None:
        """Decode the Bearer token and return the claim as ``TenantId``.

        Returns ``None`` if Authorization header missing / not Bearer.
        Raises ``TenantExtractionError`` if decode fails or claim missing.
        """
        auth = request.get_header("Authorization") or ""
        if not auth.startswith(_BEARER_PREFIX):
            return None
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
