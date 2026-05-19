# Dual-Pattern: Observability + Audit Bus

TenantShield exposes two independent emission paths that operate at
different semantic levels:

| Path | Logger namespace | Granularity | Typical use |
|---|---|---|---|
| **Observability** | `tenantshield.observability` | Operation / lifecycle | Diagnostics, traces, metrics |
| **Audit bus** | `tenantshield.audit` (via `StructLogSink`) | Policy / decision | Compliance, SIEM, security records |

The two paths are independent by construction: enabling one does not
enable the other; disabling one does not affect the other.

## Independent gating

```python
# Observability: configure(emit_events=True/False)
from tenantshield.observability import configure
configure(emit_events=True)

# Audit: register a sink to receive events
from tenantshield import register_sink, StructLogSink
register_sink(StructLogSink())
```

Adopter matrix:

| Observability | Audit sink registered | Outcome |
|---|---|---|
| disabled | none | Zero log volume (library default) |
| enabled | none | Operational events only |
| disabled | one or more | Audit / compliance events only |
| enabled | one or more | Both (complementary) |

## Why two layers?

Audit events carry **policy / security** intent (Sub-phase 1B):

- `CONTEXT_BOUND` / `CONTEXT_RELEASED` -- a tenant scope was active.
- `POLICY_ALLOW` / `POLICY_DENY` -- a policy evaluation reached a decision.
- `ENFORCEMENT_VIOLATION` -- a cross-tenant write was attempted.
- `SINK_FAILURE` -- a sink raised; bus recovered.

Observability events carry **operation / lifecycle** intent (Sub-fase 5B):

- Scope lifecycle (`tenant.scope.*`).
- Enforcement operation flow (`tenant.write.*`, `tenant.read.*`).
- Middleware request boundaries (`tenant.middleware.*`).

A SIEM does not need every `do_orm_execute` fallthrough. A trace dashboard
does not need every `POLICY_ALLOW`. The split lets adopters route each
stream to the appropriate sink without filtering at the call site.

## Dual-dispatch for security-critical events

`tenant.write.blocked` (observability) and `ENFORCEMENT_VIOLATION` (audit)
fire together at every cross-tenant write site (INSERT / UPDATE / DELETE,
mismatch / missing). Adopters who only register an audit sink still
receive the `ENFORCEMENT_VIOLATION` record even with observability
disabled.

```python
# Audit sink receives ENFORCEMENT_VIOLATION even if observability is OFF
from tenantshield import register_sink, InMemorySink, AuditEventType
sink = InMemorySink()
register_sink(sink)

# ... cross-tenant write attempt ...

violations = [e for e in sink.events
              if e.event_type == AuditEventType.ENFORCEMENT_VIOLATION]
assert len(violations) >= 1
```

## See also

- [Quick Start](quick-start.md).
- [Production Checklist](production-checklist.md) -- audit sink is
  recommended for production deployments.
