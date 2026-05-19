# ADR-0012 -- Audit-observability dual-pattern

**Status:** Accepted.
**Date:** 2026-05-18.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.
**Related:** Decision 7-A (audit logger separation) from the Phase 5
kickoff Mass A ratification; DR-042; ADR-0011 (observability
architecture -- complementary emission layer); Sub-phase 1B audit
module (``src/tenantshield/audit.py``).

## Context

TenantShield ships two structured emission paths after Phase 5:

- **Audit bus** (Sub-phase 1B, since tag ``v0.0.3-alpha.0``, commit
  ``02667b8``). A sink-based event bus emitting at policy / decision
  granularity. Adopter API:
  ``register_sink(StructLogSink())``.
- **Observability** (Sub-fase 5B, this Phase). A structlog-based
  emission module at operation / lifecycle granularity (see
  ADR-0011). Adopter API:
  ``configure(emit_events=True)``.

The audit bus was the canonical TenantShield observability mechanism
since Phase 1B per roadmap §1.5 ("Observabilidad por defecto: cada
bloqueo, cada inyección de filtro, cada propagación de contexto emite
eventos auditables"). Sub-fase 5B introduces a second layer at a
finer semantic level. The architectural question this ADR answers:
how do the two layers coexist?

Sub-tarea 5B.1.5 empirically inspected the pre-existing audit
infrastructure and surfaced two key findings:

- ``StructLogSink`` already uses
  ``structlog.get_logger("tenantshield.audit")`` by default
  (``audit.py:138``). Decision 7-A's "dedicated audit logger
  namespace" requirement is operational by construction.
- ``AuditEventType.ENFORCEMENT_VIOLATION`` was defined since Sub-phase
  1B (``audit.py:43``) but had **zero emission sites** in productive
  code. The architectural intent (cross-tenant write attempts emit
  ``ENFORCEMENT_VIOLATION``) was reserved but never realized.

Sub-tarea 5B.5.0 empirical exploration ratified Option (c) from the
post-finding resolution matrix: do NOT create a new audit logger
namespace (it exists); INTEGRATE observability emission with the
existing audit bus for security-critical events. This ADR documents
the integration architecture.

## Decision

Adopt a **dual-pattern** emission architecture where the audit bus and
observability emit at different semantic levels, gated independently,
with explicit dual-dispatch at security-critical sites.

### Architectural pillars

1. **Semantic separation by granularity (DR-042).** The two layers
   emit at different abstraction levels:

   | Layer | Logger namespace | Granularity | Typical consumer |
   |---|---|---|---|
   | Audit bus | ``tenantshield.audit`` | Policy / decision | SIEM, compliance archive |
   | Observability | ``tenantshield.observability`` | Operation / lifecycle | Trace store, metrics, diagnostics |

   AuditEventType (6 values) sits at policy granularity:
   ``CONTEXT_BOUND`` / ``CONTEXT_RELEASED`` / ``POLICY_ALLOW`` /
   ``POLICY_DENY`` / ``ENFORCEMENT_VIOLATION`` / ``SINK_FAILURE``.
   The observability 9-event taxonomy sits at operation granularity
   (see ADR-0011). The two taxonomies are complementary, not
   duplicative; a single conceptual event (a cross-tenant write
   attempt) is recorded at both layers with different field shapes
   suited to different consumers.

2. **Decision 7-A separation by independent gating mechanisms.** The
   two layers operate under distinct gates:

   - Audit emission gated by the sink registry: adopter must
     ``register_sink(...)`` to observe events.
   - Observability emission gated by the module flag: adopter must
     ``configure(emit_events=True)`` to enable.

   Empirically verified in Sub-tarea 5B.5.0 via 3-scenario matrix:

   | obs.is_enabled() | sink registered | obs emit | audit emit |
   |---|---|---|---|
   | False | yes | 0 | 1 |
   | True | yes | 1 | 1 |
   | True | no | 1 | 0 |

   The mechanisms are decoupled by construction. Adopters choose any
   combination (audit only / observability only / both / neither)
   without one path interfering with the other.

3. **ENFORCEMENT_VIOLATION dual-dispatch at WRITE_BLOCKED sites
   (DR-042; Sub-tarea 5B.5.1).** At every cross-tenant write site
   (INSERT mismatch + UPDATE missing/mismatch + DELETE missing/mismatch
   = 5 sites in ``events.py``) the integration emits both
   ``tenant.write.blocked`` (observability) and
   ``AuditEvent(event_type=ENFORCEMENT_VIOLATION, ...)`` (audit).
   Adopters who only register an audit sink still capture
   ``ENFORCEMENT_VIOLATION`` regardless of observability state -- the
   security-critical signal is registry-gated, not flag-gated.

4. **Helper-pattern for dual-dispatch (Option (ii); Sub-tarea 5B.5.0
   ratified).** A module-local helper
   ``_emit_enforcement_violation_audit(ctx, attempted_tenant_id,
   mapper, operation)`` consolidates the audit emission at the 5
   sites. Pattern paralelo ``policies.evaluate_and_audit`` precedent
   from Sub-phase 1B. Direct ``audit_emit(...)`` call inside the
   helper preserves Decision 7-A: observability ``is_enabled()`` does
   NOT gate audit emission.

5. **Pre-existing audit emission sites preserved.** Sub-phase 1B
   already emits ``CONTEXT_BOUND`` / ``CONTEXT_RELEASED`` at every
   ``tenant_scope`` / ``atenant_scope`` entry/exit
   (``context.py``:78, 83, 141, 146) and ``POLICY_ALLOW`` /
   ``POLICY_DENY`` via ``policies.evaluate_and_audit``. Observability
   emits the complementary operation-level events (``tenant.scope.*``,
   ``tenant.write.*``, ``tenant.read.*``, ``tenant.middleware.*``).
   No removal, no rewrite; only addition of
   ``ENFORCEMENT_VIOLATION`` at the previously-empty enforcement gap.

### Architectural outcome

After Sub-tarea 5B.5.1, ``AuditEventType`` has 5 of 6 values emitted
in productive code (only ``SINK_FAILURE`` is bus-internal, emitted by
the bus's own error-recovery path when a registered sink raises). The
Sub-phase 1B architectural intent -- every enforcement decision
visible at the audit layer -- is finally fully realized.

## Alternatives considered

### Alternative A -- Inline dual-dispatch at each emission site

Repeat the ``audit_emit(AuditEvent(...))`` call inline at each of the
5 ``WRITE_BLOCKED`` sites, mirroring the ``context.py`` inline
emission style.

**Rejected because:**

- 5 sites with identical payload structure produce ~30-40 LOC of
  repetition. If the ``AuditEvent`` contract evolves (new fields,
  payload reshape), 5 edits required vs 1.
- Project precedent supports helper-pattern via
  ``policies.evaluate_and_audit``; the helper approach is the closer
  fit for multi-site emission.

### Alternative B -- Auto-chain audit emission from ``emit_event``

Modify ``emit_event`` to detect security-critical event names and
dispatch ``audit_emit(...)`` after the structlog emission.

**Rejected because:**

- ``emit_event`` early-returns when observability is disabled. Chaining
  audit emission inside ``emit_event`` would gate audit by
  ``is_enabled()``, violating Decision 7-A's "audit operates
  independently of this configuration" requirement.
- Couples the observability module to audit module imports, breaking
  the layer separation.
- Implicit behavior at the observability emission site is harder to
  audit (pun intended) during code review than an explicit helper
  invocation.

### Alternative C -- Unified single-layer emission

Replace the audit bus with the observability module entirely; emit
only via structlog, retire ``AuditEvent`` / ``AuditSink`` / ``emit``.

**Rejected because:**

- Sub-phase 1B audit infrastructure is **mature and adopter-facing**:
  228 LOC, 29 tests, documented in ``docs/getting-started.md``
  (``register_sink(StructLogSink())`` is the canonical onboarding
  pattern), 10 public symbols re-exported at top level.
- Audit bus's sink-and-registry pattern serves SIEM-bound retention
  models where adopters route audit events to dedicated infrastructure
  separate from operational telemetry. Forcing SIEM through structlog
  + processor chain loses the architectural distinction.
- ``StructLogSink`` already gives adopters the structlog path if they
  want it; no migration friction to consolidate.

## Consequences

### Positive

- Decision 7-A operational by construction + verified empirically at
  runtime (Sub-tarea 5B.5.1 boundary test).
- Sub-phase 1B audit infrastructure preserved without modification;
  pre-existing 29 audit tests continue to pass unchanged.
- ``ENFORCEMENT_VIOLATION`` emission gap filled: 5 of 6
  ``AuditEventType`` values now emit in productive code.
- Adopter dual-API mental model documented in
  ``docs/observability/dual-pattern.md`` (Sub-fase 5B.6).
- Adopter combinations (audit only / observability only / both /
  neither) all valid; each layer's gate is the canonical control.

### Negative

- Dual emission at security sites: every cross-tenant write triggers
  two emission paths. Cost is acceptable because ``WRITE_BLOCKED``
  is a rare security event (0..1 per request, often 0). Hot-path
  enforcement events (``READ_FILTERED``, ``WRITE_INJECTED``,
  ``READ_FALLTHROUGH``) emit observability only -- no audit
  dual-dispatch.
- Adopters need to understand both APIs to use either fully. Mitigation
  via Sub-fase 5B.6 documentation, specifically
  ``docs/observability/dual-pattern.md`` which contrasts the two
  layers in a single page.

## Empirical evidence

Sub-tareas 5B.1.5, 5B.5.0, and 5B.5.1 empirically validated:

- 5B.1.5 (audit module inspection mini-tarea) -- mapped 4 existing
  audit emission sites + 1 gap (``ENFORCEMENT_VIOLATION``).
  ``StructLogSink`` confirmed using ``tenantshield.audit`` namespace
  by default.
- 5B.5.0 (dual-dispatch empirical exploration) -- 3 scenarios
  verifying Decision 7-A independent gating; AuditEvent contract
  correction (uses ``tenant_context`` + ``payload``, NOT
  ``tenant_id`` + ``details``); 3-option architectural analysis with
  Option (iii) "auto-chain" eliminated as Decision 7-A violation.
- 5B.5.1 (ENFORCEMENT_VIOLATION dual-dispatch productive integration)
  -- helper ``_emit_enforcement_violation_audit`` materialized at 5
  WRITE_BLOCKED sites; 7 tests covering INSERT / UPDATE / DELETE
  mismatch + Decision 7-A boundary + payload structure; runtime smoke
  confirmed ``ENFORCEMENT_VIOLATION`` fires when observability is
  disabled (audit sink only path).

## References

- DR-042 -- Dedicated audit logger separation (Decision 7-A
  consummation).
- ADR-0011 -- Observability architecture (complementary emission
  layer at operation granularity).
- ``src/tenantshield/audit.py`` -- Sub-phase 1B audit bus
  (``AuditEvent``, ``AuditEventType``, ``AuditSink``, ``StructLogSink``,
  ``register_sink``, ``unregister_sink``, ``emit``).
- ``src/tenantshield/context.py`` -- ``CONTEXT_BOUND`` /
  ``CONTEXT_RELEASED`` emission sites (lines 78, 83, 141, 146).
- ``src/tenantshield/policies.py`` -- ``POLICY_ALLOW`` /
  ``POLICY_DENY`` emission via ``evaluate_and_audit`` (lines 197,
  199).
- ``src/tenantshield/adapters/sqlalchemy/events.py`` --
  ``ENFORCEMENT_VIOLATION`` dual-dispatch at 5 ``WRITE_BLOCKED``
  sites (Sub-tarea 5B.5.1 commit ``1da77fc``).
- ``docs/observability/dual-pattern.md`` -- adopter-facing
  documentation of the dual-pattern (Sub-fase 5B.6).
- Roadmap §1.5 ("Observabilidad por defecto") -- foundational
  architectural principle.

---

**End of ADR-0012.**
