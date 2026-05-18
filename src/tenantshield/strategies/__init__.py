"""Cross-adapter tenant extraction strategies (top-level core module).

Per Decision 4-A from the Phase 4 kickoff: framework-agnostic tenant
extraction strategies live at top-level ``tenantshield.strategies``,
not under any specific adapter namespace. Adapters re-export from here
preserving backward-compatible import paths (Decision 6-A; Django
adapter re-export shim materialized in Sub-fase 4B Tarea 4B.2).

Public API
----------

- :class:`RequestProtocol` -- framework-agnostic request interface.
- :class:`TenantExtractionStrategy` -- protocol for strategy
  implementations.
- :class:`TenantExtractionError` -- raised on irrecoverable extraction
  failure (distinct from strategy fall-through return ``None``).
- :class:`HeaderStrategy` -- extract from HTTP header.
- :class:`HostStrategy` -- extract from request host's leftmost
  subdomain segment (Decision 5-B: replaces Django-specific
  ``SubdomainStrategy``).
- :class:`JWTStrategy` -- extract from JWT Bearer token claim.
- :class:`CallableStrategy` -- delegate to adopter-supplied callable.

``resolve_strategy()`` factory function deferred to Sub-fase 4B Tarea
4B.4 (SA adapter analog of Phase 2B Django ``resolve_strategy``).

Strategy contract semantics
---------------------------

- Return ``TenantId`` on successful extraction.
- Return ``None`` when the strategy does not apply (e.g., header
  absent, no subdomain, no Authorization header). Middleware treats
  this as fall-through.
- Raise ``TenantExtractionError`` when the strategy applies but
  extraction fails irrecoverably (malformed JWT, missing required
  claim, callable raises diagnostic state).

Adapter shims may translate this two-tier contract to a single-tier
raise-on-missing model for backward compatibility with their original
API (e.g., the Django adapter's Phase 2B raise-on-missing semantics
are preserved by the Sub-fase 4B Tarea 4B.2 shim layer).
"""

from __future__ import annotations

from tenantshield.strategies._resolver import resolve_strategy
from tenantshield.strategies.base import (
    RequestProtocol,
    TenantExtractionError,
    TenantExtractionStrategy,
)
from tenantshield.strategies.callable_ import CallableStrategy
from tenantshield.strategies.header import HeaderStrategy
from tenantshield.strategies.host import HostStrategy
from tenantshield.strategies.jwt import JWTStrategy

__all__ = [
    "CallableStrategy",
    "HeaderStrategy",
    "HostStrategy",
    "JWTStrategy",
    "RequestProtocol",
    "TenantExtractionError",
    "TenantExtractionStrategy",
    "resolve_strategy",
]
