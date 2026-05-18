"""Base protocols and exceptions for tenant extraction strategies.

This module defines the framework-agnostic foundation for cross-adapter
tenant strategies (Decision 4-A from the Phase 4 kickoff). Strategies
receive ``RequestProtocol``-conforming objects; framework adapters wrap
their native request objects (Django ``HttpRequest``, ASGI scope dict,
WSGI environ) to expose this minimal surface.

Phase 2B precedent observed: Django strategies were originally typed
against ``HttpRequest`` directly, coupling them to Django's WSGI
``META`` dict and ``get_host()`` method. Sub-fase 4B Tarea 4B.0
empirically determined a 2-method ``RequestProtocol`` surface
sufficient for all four strategy implementations + cross-adapter
adapter wrapper pattern (BLOCKER #30 deferral closed; see ADR-0010).

Strategy contract semantics:

- Returns ``TenantId`` when extraction succeeds.
- Returns ``None`` when the strategy does not apply to the request
  (e.g., header absent, host has no subdomain, JWT Authorization
  missing). Middleware treats ``None`` as fall-through to the
  configured ``on_missing_tenant`` behavior.
- Raises ``TenantExtractionError`` when the strategy applies but
  extraction fails irrecoverably (malformed JWT, missing claim,
  callable raises). Middleware surfaces this to adopters as a
  diagnostic signal distinct from fall-through.

Adapter-level shims (Sub-fase 4B Tarea 4B.2) translate this two-tier
contract back to the Django-adapter raise-on-missing semantics for
backward compatibility (Decision 6-A).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from tenantshield._types import TenantId


@runtime_checkable
class RequestProtocol(Protocol):
    """Framework-agnostic request interface for tenant extraction.

    Adapters wrap framework-specific request objects to conform. Two
    methods cover all four built-in strategies' empirical needs
    (Tarea 4B.0 findings):

    - ``get_header(name)``: case-insensitive header lookup, returns
      header value or ``None`` if absent.
    - ``get_host()``: returns the request's host string, including
      port if present (e.g., ``"acme.example.com:8080"``).

    ``@runtime_checkable`` enables ``isinstance(obj, RequestProtocol)``
    for ergonomic test fixtures + adapter wrapper conformance checks.
    """

    def get_header(self, name: str) -> str | None:
        """Return header value by name (case-insensitive), or ``None``."""
        ...

    def get_host(self) -> str:
        """Return host string (may include port).

        Example return values: ``"acme.example.com"``,
        ``"acme.example.com:8080"``, ``"localhost"``.
        """
        ...


class TenantExtractionError(Exception):
    """Raised when a strategy applies but extraction fails irrecoverably.

    Distinct from strategy fall-through (return ``None``). Adopters
    surface this as a diagnostic signal (malformed JWT, missing
    required claim, callable strategy raised internally).

    Args:
        strategy_name: Name of the strategy class that raised, for
            diagnostic logging.
        reason: Human-readable reason for the failure.
        context: Optional mapping of additional diagnostic context
            (header name, claim name, etc.).
    """

    def __init__(
        self,
        *,
        strategy_name: str,
        reason: str,
        context: dict[str, object] | None = None,
    ) -> None:
        self.strategy_name = strategy_name
        self.reason = reason
        self.context = context or {}
        super().__init__(f"{strategy_name}: {reason}")


@runtime_checkable
class TenantExtractionStrategy(Protocol):
    """Protocol for tenant extraction strategies operating on RequestProtocol.

    Implementations declare conformance structurally; explicit
    inheritance is not required.
    """

    def extract(self, request: RequestProtocol) -> TenantId | None:
        """Extract tenant identifier from request.

        Returns:
            ``TenantId`` if the strategy successfully extracted a
            tenant; ``None`` if the strategy does not apply to this
            request (fall-through semantics).

        Raises:
            TenantExtractionError: If the strategy applies but
                extraction fails (malformed token, missing required
                claim, callable raised, etc.).
        """
        ...
