"""Django adapter-specific exceptions.

These are distinct from the core exceptions in tenantshield.exceptions:
they are raised by the adapter layer (extraction strategies) and
typically translated to MissingTenantContextError at the middleware
boundary.

The separation prevents tight coupling between strategy implementations
and the core exception hierarchy: a strategy that cannot extract a
tenant raises a TenantExtractionError describing what failed; the
middleware decides what to do (raise the core exception, return 404,
bind a public tenant, etc.) per the configured on_missing_tenant
behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class TenantExtractionError(Exception):
    """Raised by an extraction strategy when no tenant can be extracted.

    Caught by TenantContextMiddleware which translates the error to the
    configured on_missing_tenant behavior (raise, 404, public, or
    callable).

    Args:
        strategy_name: Class name of the strategy that raised (used for
            diagnostics).
        reason: Human-readable reason for the failure.
        context: Optional context dict for structured logging.
    """

    def __init__(
        self,
        strategy_name: str,
        reason: str,
        context: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(reason)
        self.strategy_name = strategy_name
        self.reason = reason
        self.context: Mapping[str, object] = context or {}
