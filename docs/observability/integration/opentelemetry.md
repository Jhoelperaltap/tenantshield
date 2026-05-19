# OpenTelemetry Integration

TenantShield observability events are emitted via structlog. The
processor chain is fully adopter-controlled, so OpenTelemetry context
propagation works without any TenantShield-side coupling.

## Pattern

Add a structlog processor that pulls the current OTel span context and
injects `trace_id` / `span_id` into every emitted event:

```python
import structlog
from opentelemetry import trace
from structlog.contextvars import merge_contextvars
from structlog.processors import JSONRenderer, TimeStamper, add_log_level


def add_otel_context(logger, method_name, event_dict):
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


structlog.configure(
    processors=[
        merge_contextvars,
        add_otel_context,
        add_log_level,
        TimeStamper(fmt="iso"),
        JSONRenderer(),
    ],
)
```

## Result

Every `tenant.scope.*`, `tenant.write.*`, `tenant.read.*`, and
`tenant.middleware.*` event now carries `trace_id` and `span_id`,
linking enforcement decisions to the request-level trace.

```json
{
  "event": "tenant.write.blocked",
  "tenant_id": "acme",
  "attempted_tenant_id": "globex",
  "model_class": "Invoice",
  "operation": "before_insert",
  "trace_id": "0af7651916cd43dd8448eb211c80319c",
  "span_id": "b7ad6b7169203331",
  "log_level": "warning",
  "timestamp": "2026-05-18T10:24:33.412Z"
}
```

## Coverage

The same processor chain decorates the audit logger
(`tenantshield.audit`) when adopters route audit events through
structlog via `StructLogSink`. OTel context propagates to both layers
without additional configuration.

## See also

- [Quick Start](../quick-start.md).
- [Prometheus integration](prometheus.md).
