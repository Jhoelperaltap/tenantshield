"""TenantShield observability emission entry point.

Sub-fase 5B.1 -- ``emit_event()`` private entry point.

Disabled-default gate pattern verified Sub-fase 5B.0 Scenario #3
(~6 ns/call overhead acceptable for enforcement hot path). The
``is_enabled()`` indirection adds a function-call hop but keeps the
hot path under the <100 ns acceptance threshold ratified there.
"""

from __future__ import annotations

import structlog

from tenantshield.observability.config import is_enabled
from tenantshield.observability.events import EVENT_SEVERITY

_logger = structlog.get_logger("tenantshield.observability")


def emit_event(name: str, **fields: object) -> None:
    """Emit a TenantShield observability event.

    Disabled-default gate: early-return if observability emission disabled.
    Severity dispatched per ``EVENT_SEVERITY`` map (Scenario #1 baseline).

    Args:
        name: Event name constant from ``tenantshield.observability.events``.
        **fields: Structured fields for emission (typically ``tenant_id``,
            ``scope_id``, ``operation``, ``model_class``).
    """
    if not is_enabled():
        return

    severity = EVENT_SEVERITY.get(name, "info")
    method = getattr(_logger, severity, _logger.info)
    method(name, **fields)
