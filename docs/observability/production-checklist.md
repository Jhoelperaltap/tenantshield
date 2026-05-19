# Production Deployment Checklist

Before deploying TenantShield to production, walk through this list. The
items below are recommended defaults; not every deployment needs every
item, but conscious decisions on each one prevent silent gaps.

## Audit bus

- [ ] **Register at least one audit sink** for compliance traceability.
  `StructLogSink()` routes audit events through your structlog stack;
  `InMemorySink()` is for tests only.
- [ ] Confirm `tenantshield.audit` logger output reaches the destination
  expected by the security or compliance team (SIEM, archive, etc.).
- [ ] Verify `ENFORCEMENT_VIOLATION` events propagate end-to-end by
  triggering a cross-tenant write in a staging environment.

## Observability

- [ ] Decide whether to enable observability:
  `tenantshield.observability.configure(emit_events=True)`. Disabled by
  default; enable when monitoring or distributed tracing is required.
- [ ] Configure the structlog processor chain in your application
  bootstrap. TenantShield does not call `structlog.configure(...)`.
- [ ] If using OpenTelemetry: prepend the OTel context processor so
  `trace_id` / `span_id` propagate into observability events.
- [ ] If using Prometheus: add a counter / histogram processor before the
  renderer.

## Middleware

- [ ] Choose `TenantSessionMiddleware` (Phase 3B + 4A) or
  `AsyncTenantSessionMiddleware` (Phase 5A) based on your stack. Both
  emit the same observability events; only `middleware_class` differs.
- [ ] Decide the `on_missing_tenant` mode:
  `"allow_unrestricted"` (fall-through, default) or `"raise"` (strict).
- [ ] Confirm the `resolve_tenant` callable cannot return surprising
  types under load (use `inspect.iscoroutine` if dual-mode).

## Tenant-aware models

- [ ] Every model that touches multi-tenant data is decorated with
  `@tenant_aware`.
- [ ] Each tenant-aware model declares a `tenant_id` column.
- [ ] Integration tests cover INSERT / UPDATE / DELETE cross-tenant
  attempts and assert that `CrossTenantAccessError` is raised.

## Logging hygiene

- [ ] `tenantshield.observability` and `tenantshield.audit` loggers go to
  separate destinations (or are tagged distinctly) so operational noise
  does not drown out security records.
- [ ] Log retention for audit events satisfies regulatory requirements
  (often longer than operational logs).

## See also

- [Quick Start](quick-start.md).
- [Dual-Pattern](dual-pattern.md).
- [Async Middleware Migration](async-middleware-migration.md).
