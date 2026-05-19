# Observability Quick Start

TenantShield emits structured events for tenant scope lifecycle,
enforcement decisions, and middleware request boundaries. Emission is
**disabled by default**; adopters enable it explicitly.

## Enable emission

```python
from tenantshield.observability import configure

configure(emit_events=True)
```

Once enabled, every active `SessionScope`, `AsyncSessionScope`, and
`TenantSessionMiddleware` request will emit events to the
`tenantshield.observability` structlog logger.

## Configure structlog (canonical)

```python
import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level
from structlog.contextvars import merge_contextvars

structlog.configure(
    processors=[
        merge_contextvars,
        add_log_level,
        TimeStamper(fmt="iso"),
        JSONRenderer(),
    ],
)
```

Adopters keep full control of the processor chain. TenantShield only
emits; it does NOT call `structlog.configure(...)` itself.

## Event taxonomy

Nine event names across three semantic groups (severity is recommended
default; adopters may filter or remap via the structlog processor chain):

| Event | Severity | When emitted |
|---|---|---|
| `tenant.scope.entered` | INFO | `SessionScope` / `AsyncSessionScope` bound a tenant |
| `tenant.scope.exited` | INFO | Scope exited cleanly |
| `tenant.scope.exception` | WARNING | Scope exited via exception |
| `tenant.write.injected` | DEBUG | `before_insert` auto-injected `tenant_id` |
| `tenant.write.blocked` | WARNING | Cross-tenant INSERT/UPDATE/DELETE attempted |
| `tenant.read.filtered` | DEBUG | `do_orm_execute` filter applied to tenant-aware entity |
| `tenant.read.fallthrough` | DEBUG | `do_orm_execute` ran without an active scope |
| `tenant.middleware.request_bound` | DEBUG | Middleware bound a tenant for the request |
| `tenant.middleware.request_unbound` | DEBUG | Middleware released the tenant scope |

## Verify

```python
from structlog.testing import capture_logs
from tenantshield.adapters.sqlalchemy import SessionScope

with capture_logs() as logs, SessionScope(tenant="acme"):
    pass

scope_events = [e["event"] for e in logs if e["event"].startswith("tenant.scope")]
assert scope_events == ["tenant.scope.entered", "tenant.scope.exited"]
```

## Disable

```python
configure(emit_events=False)
```

The disabled path adds about 6 nanoseconds per call site (empirically
benchmarked); production cost is effectively zero when emission is off.

## See also

- [Dual-Pattern](dual-pattern.md) -- combining observability with the
  audit bus for security-critical events.
- [OpenTelemetry integration](integration/opentelemetry.md).
- [Prometheus integration](integration/prometheus.md).
- [Production Checklist](production-checklist.md).
