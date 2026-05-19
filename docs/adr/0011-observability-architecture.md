# ADR-0011 -- Observability architecture for Sub-fase 5B

**Status:** Accepted.
**Date:** 2026-05-18.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.
**Related:** Decisions 4-A (event taxonomy), 5-A (structlog emission),
6-A (disabled-default) from the Phase 5 kickoff Mass A ratification;
DR-039 through DR-044; ADR-0009 (AsyncSession adapter -- shared
ContextVar mechanism enables async observability without new event
listeners); ADR-0010 (cross-adapter strategy unification -- orthogonal
to observability); ADR-0012 (audit dual-pattern -- complementary
emission layer).

## Context

Phase 5 of TenantShield is production hardening for multi-adopter
distribution. Pre-Phase-5 the project shipped a comprehensive Sub-phase
1B audit bus (228 LOC, 29 tests, adopter-facing via
``register_sink(StructLogSink())``) emitting **policy / decision**
granularity events (``POLICY_ALLOW`` / ``POLICY_DENY`` /
``ENFORCEMENT_VIOLATION`` / ``CONTEXT_BOUND`` / ``CONTEXT_RELEASED`` /
``SINK_FAILURE``).

The audit bus is necessary but insufficient for production observability.
Adopters running TenantShield in production also need **operation /
lifecycle** granularity events for diagnostics, traces, and metrics:

- Did the middleware bind a tenant for this request?
- Did ``do_orm_execute`` filter the query, or did the query escape into
  fall-through mode?
- Did ``before_insert`` auto-inject a tenant_id?
- Did the scope exit cleanly, or did an exception unwind it?

These questions are below the audit bus's policy granularity. Forcing
adopters to derive operation-level signal from policy-level audit events
would couple SIEM-bound retention with high-volume operational
telemetry -- the opposite of what production deployments need.

Sub-fase 5B introduces a second emission layer at operation /
lifecycle granularity, gated independently from the audit bus. This
ADR documents the architectural decision.

## Decision

Introduce ``tenantshield.observability`` as a structured event emission
module operating at operation / lifecycle granularity, complementary to
the Sub-phase 1B audit bus.

### Architectural pillars

1. **9-event taxonomy (Decision 4-A; DR-039).** Three semantic groups
   spanning the enforcement surface:

   | Group | Event | Severity | Frequency |
   |---|---|---|---|
   | Scope lifecycle | ``tenant.scope.entered`` | INFO | 1 per scope binding |
   | Scope lifecycle | ``tenant.scope.exited`` | INFO | 1 per scope binding |
   | Scope lifecycle | ``tenant.scope.exception`` | WARNING | 0..1 per scope |
   | Enforcement | ``tenant.write.injected`` | DEBUG | 0..N per request |
   | Enforcement | ``tenant.write.blocked`` | WARNING | 0..1 per request |
   | Enforcement | ``tenant.read.filtered`` | DEBUG | 0..N per request |
   | Enforcement | ``tenant.read.fallthrough`` | DEBUG | 0..N per request |
   | Middleware | ``tenant.middleware.request_bound`` | DEBUG | 1 per request |
   | Middleware | ``tenant.middleware.request_unbound`` | DEBUG | 1 per request |

   Severity distribution (5 DEBUG / 2 INFO / 2 WARNING) was empirically
   informed via Sub-fase 5B.0 Scenario #1 -- high-volume operational
   events default to DEBUG so production log volume stays bounded
   without adopter filter configuration.

2. **structlog as emission mechanism (Decision 5-A; DR-040).**
   ``structlog`` was already pinned as a base dependency (DR-010, ``>=25.0,<26.0``)
   to support ``StructLogSink``. Reusing it for observability adds
   zero new transitive dependencies. The adopter-extensible processor
   chain enables canonical OpenTelemetry / Prometheus integration without
   TenantShield-side coupling.

3. **Disabled-by-default emission control (Decision 6-A; DR-041).**
   ``configure(emit_events=False)`` is the default. Adopters explicitly
   call ``configure(emit_events=True)`` to enable. The disabled gate
   adds ~6 ns/call overhead (empirically benchmarked in Sub-fase 5B.0
   Scenario #3 over 1 M iterations), well under the <100 ns acceptance
   threshold. Phase 4 adopters who do not enable observability
   experience zero log volume change.

4. **Distinct logger namespace.** Events route via
   ``structlog.get_logger("tenantshield.observability")``. The audit
   bus uses ``tenantshield.audit`` (per Sub-phase 1B
   ``StructLogSink`` default). Separation by namespace lets adopters
   route operational telemetry and security audit to distinct
   destinations.

5. **Emission integration without architectural disruption.**
   Observability emission is additive at every site:

   - ``SessionScope`` / ``AsyncSessionScope`` -- emission around the
     ``yield`` inside the existing ``with _tenant_scope(ctx):`` block
     (Tarea 5B.2).
   - ``before_insert`` / ``before_update`` / ``before_delete`` /
     ``do_orm_execute`` -- emission at existing decision sites (Tarea
     5B.3).
   - Three middleware variants (``TenantSessionMiddleware``,
     ``AsyncTenantSessionMiddleware``, ``TenantSessionMiddlewareWSGI``)
     -- emission around the scope ctx mgr in each ``__call__`` (Tarea
     5B.4).

   Phase 3A event-based enforcement architecture untouched. Phase 4A
   AsyncSession coverage inherited transitively via
   ``AsyncSession.sync_session_class = Session`` event delegation: the
   same event listeners that fire for ``Session`` operations fire for
   ``AsyncSession`` operations, so observability emission applies to
   both sync and async paths without separate registration.

6. **Adopter-extensible processor chain (DR-043).** Adopters configure
   their own structlog processor chain; TenantShield does NOT call
   ``structlog.configure(...)`` itself. OpenTelemetry context
   propagation (``trace_id`` / ``span_id``) and Prometheus metric
   emission compose as custom processors prepended to the chain.

## Alternatives considered

### Alternative A -- Extend the audit bus instead

Add observability events to ``AuditEventType`` and route them through
the existing sink registry.

**Rejected because:**

- Audit retention requirements (SIEM-bound, often years-long) collide
  with operational telemetry retention requirements (days-to-weeks,
  high volume). Forcing operational events through audit-graded
  storage is wasteful and complicates compliance posture.
- Audit emission is always-on (registry-gated); observability needs
  disabled-default for cost-conscious production deployments where
  enforcement runs but no telemetry is exported. The audit bus has no
  per-event gate.
- The ``AuditEvent`` payload contract (``tenant_context``, ``payload``,
  ``timestamp``) is policy-shaped; operational events want flat
  fields (``tenant_id``, ``model_class``, ``operation``, ``scope_class``)
  for direct ingestion into trace / metric stores.

### Alternative B -- Python stdlib logging instead of structlog

Use ``logging.getLogger("tenantshield.observability")`` for emission.

**Rejected because:**

- structlog is already pinned as a base dep (DR-010) and offers
  structured-field-first emission; routing through stdlib ``logging``
  would force adopters to add a JSON formatter or accept positional
  ``%s`` interpolation.
- ``structlog.contextvars`` integrates cleanly with asyncio
  ``copy_context()`` semantics (empirically validated in Sub-fase 5B.0
  Scenario #2); stdlib ``logging`` requires manual ``extra=...`` dict
  passing per call.
- Adopters who prefer stdlib can still receive structlog output via the
  ``structlog.stdlib.LoggerFactory`` adapter; the reverse path (lift
  stdlib to structured fields) is more friction.

### Alternative C -- Always-on emission

Emit unconditionally; let adopters filter at the logger / processor
level if they want zero output.

**Rejected because:**

- Zero overhead by default is canonical for opt-in production features.
  Phase 4 adopters who never call ``configure(emit_events=True)``
  should pay no cost.
- Conditional gate is one branch (~6 ns) vs full emit path
  (microseconds). The gate amortizes well across the per-request
  enforcement hot path.
- ``structlog`` filter processors can suppress output but still pay the
  event-dict construction cost.

## Consequences

### Positive

- Production-grade observability without dependency expansion.
- Adopter-extensible integration with OpenTelemetry / Prometheus /
  custom processors (DR-043; Sub-fase 5B.6 documentation).
- Disabled-default preserves Phase 4 adopter zero log volume; ~6 ns/call
  overhead under the <100 ns acceptance threshold.
- Phase 3A + 4A architecture untouched; emission is additive at every
  site.
- Async / sync paths share emission via ``sync_session_class``
  delegation -- single integration point, dual-path coverage.

### Negative

- The 9-event taxonomy is a first-cut empirical baseline. Future events
  (e.g., per-query metrics, schema migration enforcement) may require
  taxonomy expansion. Mitigation: the taxonomy module
  (``observability/events.py``) is the single source of truth; growth
  is additive.
- Adopters must explicitly enable observability and configure the
  structlog processor chain. Discoverability friction mitigated via the
  Sub-fase 5B.6 documentation (``docs/observability/``).
- Two emission layers (observability + audit bus) require adopter
  comprehension of the dual-pattern -- see ADR-0012.

## Empirical evidence

Sub-fase 5B Tareas 5B.0 through 5B.4 empirically validated:

- 5B.0 Scenario #1 -- 9-event severity tiering empirical baseline
  (5 DEBUG / 2 INFO / 2 WARNING).
- 5B.0 Scenario #2 -- ``structlog.contextvars`` + asyncio: 4 emissions
  across awaits all carried bound context; concurrent ``asyncio.gather``
  with 3 tasks preserved per-task isolation.
- 5B.0 Scenario #3 -- disabled-default gate overhead: 6.1 ns/call
  (target <100 ns) over 1 M iterations.
- 5B.0 Scenario #4 -- OpenTelemetry / Prometheus adapter integration:
  zero TenantShield-side coupling required; adopter prepends own
  processor.
- 5B.0 Scenario #5 -- logger namespace separation: distinct logger
  instances; boundary preserved across observability + audit.
- 5B.1 -- module scaffolding (4 module files; 12 tests; 100% module
  coverage).
- 5B.2 -- scope lifecycle events integration (3 events; 11 tests;
  fall-through case emits NO scope events to preserve "scope events
  imply tenant bound" semantic).
- 5B.3 -- enforcement events integration (4 events; 12 tests; 8
  emission sites across ``before_insert`` / ``before_update`` /
  ``before_delete`` / ``do_orm_execute``).
- 5B.4 -- middleware events integration (2 events × 3 middleware
  variants; 9 tests; canonical emission ordering verified
  ``request_bound -> scope.entered -> scope.exited -> request_unbound``).

## References

- DR-039 -- 9-event observability taxonomy + severity tiering.
- DR-040 -- structlog-based emission mechanism.
- DR-041 -- Disabled-by-default emission control.
- DR-043 -- Adopter integration patterns (OpenTelemetry / Prometheus).
- DR-044 -- Async / sync integration testing methodology.
- DR-010 -- ``structlog`` as base dependency.
- ADR-0009 -- AsyncSession adapter architecture (Sub-fase 4A;
  ``sync_session_class`` delegation enables async observability
  coverage via shared event listeners).
- ADR-0010 -- Cross-adapter strategy unification (Sub-fase 4B;
  orthogonal to observability).
- ADR-0012 -- Audit-observability dual-pattern (complementary emission
  layer at policy granularity).
- Sub-fase 5B kickoff: 8-decision Mass A ratification (Decisions 4-A,
  5-A, 6-A directly load-bearing for this ADR).
- ``docs/observability/`` -- adopter integration documentation (Sub-fase
  5B.6).
- Rule 60 (ADR cross-reference cleanup) -- applied via the ADR-0009 +
  ADR-0010 + ADR-0012 cross-references.

---

**End of ADR-0011.**
