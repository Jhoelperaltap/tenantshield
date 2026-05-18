"""TenantShield observability -- structured event emission.

Sub-fase 5B production hardening feature. Disabled by default; adopters
enable via ``configure(emit_events=True)``.

Public API:
    ``configure(emit_events: bool)``: enable/disable observability emission.
    ``is_enabled() -> bool``: query current emission state.
    ``EVENT_*``: 9-event taxonomy constants (see ``events`` module).
    ``EVENT_SEVERITY``: severity tiering map.
    ``ALL_EVENTS``: full event tuple.

See ADR-0011 (observability architecture, pending materialization 5B.7).
"""

from tenantshield.observability.config import configure, is_enabled
from tenantshield.observability.events import (
    ALL_EVENTS,
    EVENT_MIDDLEWARE_REQUEST_BOUND,
    EVENT_MIDDLEWARE_REQUEST_UNBOUND,
    EVENT_READ_FALLTHROUGH,
    EVENT_READ_FILTERED,
    EVENT_SCOPE_ENTERED,
    EVENT_SCOPE_EXCEPTION,
    EVENT_SCOPE_EXITED,
    EVENT_SEVERITY,
    EVENT_WRITE_BLOCKED,
    EVENT_WRITE_INJECTED,
)

__all__ = [
    "ALL_EVENTS",
    "EVENT_MIDDLEWARE_REQUEST_BOUND",
    "EVENT_MIDDLEWARE_REQUEST_UNBOUND",
    "EVENT_READ_FALLTHROUGH",
    "EVENT_READ_FILTERED",
    "EVENT_SCOPE_ENTERED",
    "EVENT_SCOPE_EXCEPTION",
    "EVENT_SCOPE_EXITED",
    "EVENT_SEVERITY",
    "EVENT_WRITE_BLOCKED",
    "EVENT_WRITE_INJECTED",
    "configure",
    "is_enabled",
]
