"""TenantShield observability events.

Sub-fase 5B.1 -- 9-event taxonomy + severity tiering canonical map.

Severity tiering empirically informed via Sub-fase 5B.0 Scenario #1:
    - DEBUG (5 events): high-volume operational events.
    - INFO (2 events): adopter-visible scope lifecycle.
    - WARNING (2 events): security-critical OR exception path.

Adopters elevate severity via structlog filter chain en production.
"""

from typing import Final

EVENT_SCOPE_ENTERED: Final[str] = "tenant.scope.entered"
EVENT_SCOPE_EXITED: Final[str] = "tenant.scope.exited"
EVENT_SCOPE_EXCEPTION: Final[str] = "tenant.scope.exception"
EVENT_WRITE_INJECTED: Final[str] = "tenant.write.injected"
EVENT_WRITE_BLOCKED: Final[str] = "tenant.write.blocked"
EVENT_READ_FILTERED: Final[str] = "tenant.read.filtered"
EVENT_READ_FALLTHROUGH: Final[str] = "tenant.read.fallthrough"
EVENT_MIDDLEWARE_REQUEST_BOUND: Final[str] = "tenant.middleware.request_bound"
EVENT_MIDDLEWARE_REQUEST_UNBOUND: Final[str] = "tenant.middleware.request_unbound"


EVENT_SEVERITY: Final[dict[str, str]] = {
    EVENT_SCOPE_ENTERED: "info",
    EVENT_SCOPE_EXITED: "info",
    EVENT_SCOPE_EXCEPTION: "warning",
    EVENT_WRITE_BLOCKED: "warning",
    EVENT_WRITE_INJECTED: "debug",
    EVENT_READ_FILTERED: "debug",
    EVENT_READ_FALLTHROUGH: "debug",
    EVENT_MIDDLEWARE_REQUEST_BOUND: "debug",
    EVENT_MIDDLEWARE_REQUEST_UNBOUND: "debug",
}


ALL_EVENTS: Final[tuple[str, ...]] = tuple(EVENT_SEVERITY.keys())
