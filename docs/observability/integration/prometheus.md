# Prometheus Integration

TenantShield observability events can drive Prometheus metrics via a
structlog processor. The processor inspects each event and updates the
appropriate `Counter` / `Histogram` before the event is rendered.

## Pattern

```python
import structlog
from prometheus_client import Counter
from structlog.contextvars import merge_contextvars
from structlog.processors import JSONRenderer, TimeStamper, add_log_level


WRITE_BLOCKED_COUNTER = Counter(
    "tenantshield_write_blocked_total",
    "Cross-tenant write attempts blocked by TenantShield.",
    labelnames=("tenant_id", "model_class", "operation"),
)

SCOPE_ENTERED_COUNTER = Counter(
    "tenantshield_scope_entered_total",
    "Tenant scopes entered.",
    labelnames=("tenant_id", "scope_class"),
)


def emit_prometheus_metrics(logger, method_name, event_dict):
    event = event_dict.get("event")
    if event == "tenant.write.blocked":
        WRITE_BLOCKED_COUNTER.labels(
            tenant_id=event_dict.get("tenant_id", "unknown"),
            model_class=event_dict.get("model_class", "unknown"),
            operation=event_dict.get("operation", "unknown"),
        ).inc()
    elif event == "tenant.scope.entered":
        SCOPE_ENTERED_COUNTER.labels(
            tenant_id=event_dict.get("tenant_id", "unknown"),
            scope_class=event_dict.get("scope_class", "unknown"),
        ).inc()
    return event_dict


structlog.configure(
    processors=[
        merge_contextvars,
        emit_prometheus_metrics,
        add_log_level,
        TimeStamper(fmt="iso"),
        JSONRenderer(),
    ],
)
```

## Cardinality caveat

Prometheus label cardinality grows multiplicatively. Tenant IDs in
labels are common but can explode in deployments with thousands of
tenants. Consider:

- Bucketing: hash the `tenant_id` into a small set of cohorts for
  high-cardinality deployments.
- Dropping the label: emit `tenant_id` only when low-cardinality.
- Selecting events: not every event needs a metric. `tenant.write.blocked`
  is high-value (security); `tenant.read.filtered` may be too noisy.

## Recommended initial set

| Event | Metric | Rationale |
|---|---|---|
| `tenant.write.blocked` | Counter | Security signal; rare; high-value |
| `tenant.scope.exception` | Counter | Error rate signal |
| `tenant.middleware.request_bound` | Counter | Traffic shape |

Add more events incrementally as monitoring needs evolve.

## See also

- [Quick Start](../quick-start.md).
- [OpenTelemetry integration](opentelemetry.md).
