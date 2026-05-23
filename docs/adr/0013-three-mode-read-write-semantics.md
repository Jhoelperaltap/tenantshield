# ADR-0013 -- Three-mode read/write semantics for @tenant_aware models

**Status:** Accepted.
**Date:** 2026-05-20.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.
**Related:** ADR-0011 (observability architecture -- dual-dispatch
pattern precedent for ``ENFORCEMENT_BYPASS`` emission); ADR-0012
(audit-observability dual-pattern -- complementary emission layer);
Phase 6 cohort handover findings #1, #10, #12, #13 from Counterbook
adopter Sprints 0-4; ADR-0015 (Counterbook adopter side -- TenantShield
upstream improvement schedule, pre-Sprint-5 pause).

## Context

TenantShield ``v0.5.0a0`` provides two access paths for
``@tenant_aware`` models:

1. ``Model.objects.*`` (default): scoped manager + validating signals.
2. ``Model._unscoped.*``: unscoped manager, **but validating signals
   still fire**.

Cohort handover from Counterbook (first productive adopter, Sprints
0-4) surfaced three related findings:

- **Finding #10** (HIGH). Legitimate admin operations
  (``roll_forward_period``, bulk migrations, periodic Celery tasks)
  need to bypass *both* the manager filter and the validating signals.
  The current workaround --
  ``with tenant_scope(bind_tenant(...)): ...`` -- artificially binds
  to a tenant context to "pretend" the caller is operating inside one.
  This is *dishonest code*: the operation is not tenant-scoped at all,
  yet the call site reads as if it were. Audit logs reflect a fake
  tenant. Reviewer mental load increases.
- **Finding #12** (CONTRACT). ``Model._unscoped.update(...)`` outside
  ``tenant_scope`` raises ``MissingTenantContextError``.
  Counterintuitive because the attribute name suggests "bypass tenant
  filtering". Adopters reasonably expect ``_unscoped`` to be a full
  escape hatch.
- **Finding #13** (CONTRACT). ``Model._unscoped.create(...)`` fails
  outside ``tenant_scope`` because ``_validate_tenant_coherence`` runs
  in ``pre_save`` (see ADR-0007), and runs *regardless of which
  manager dispatched the save*. The signal is per-instance, not
  per-manager.

These findings reveal that the current 2-mode model conflates two
distinct concerns:

- **What rows you see.** Manager filter behavior. This is the
  ``objects`` vs ``_unscoped`` distinction.
- **What rows you can mutate without tenant context.** Signal
  validation behavior. The current implementation gates this on
  ``tenant_scope``, not on the manager.

The two concerns happen to be coupled in the default path, but they
are orthogonal in principle. ADR-0007 (event-based enforcement)
explicitly states that signal validation is "the second line of
defense" -- independent from manager filtering. Once stated as
orthogonal, a third mode follows naturally: unscoped *and* unvalidated,
for legitimate administrative use cases.

## Decision drivers

- **Counterbook KG-003 blocked.** Four sprints of accumulated
  technical debt on individual INSERTs because no explicit write-bypass
  API exists. Each admin write currently requires either a fake
  ``tenant_scope`` (Pattern A) or a per-call SQL fallback
  (``Model.objects.using(connection).raw(...)``, Pattern B). Neither
  is sustainable as the adopter codebase grows.
- **Defense-in-depth correctness.** The current ``_unscoped`` behavior
  is architecturally correct *as a read-only path*. Findings #12 and
  #13 are contract reinforcements, not bugs. The fix is not to weaken
  signal validation on ``_unscoped``; it is to provide a separate API
  for legitimate write bypass.
- **Compliance posture.** Enterprise / SOC2 audit posture requires
  that signal-bypassing writes emit an observable audit event.
  ``ENFORCEMENT_VIOLATION`` (raised on cross-tenant attempts) and a
  new ``ENFORCEMENT_BYPASS`` (emitted on intentional bypass) jointly
  give SIEM operators a complete picture of "what went around the
  enforcement layer and why".
- **Adopter mental model clarity.** A 3-mode API is teachable in a
  single sentence: "default, read-only escape, write escape". The
  current 2-mode-plus-workaround pattern is a footgun under reviewer
  time pressure.

## Considered options

- **A. (selected)** Three-mode explicit API: ``Model.objects``,
  ``Model._unscoped``, ``Model._unsafe_unscoped`` (new).
- **B.** Keep 2-mode + document ``_unscoped`` as read-only by design
  only. Leaves Finding #10 unresolved.
- **C.** Add a ``bypass_signals=True`` keyword argument to existing
  ``_unscoped`` operations. Lower surface area but per-call
  configuration; easy to miss in code review.
- **D.** Implement ``_unsafe_unscoped`` as a context manager only (no
  manager attribute). Harder to use with bulk operations
  (``bulk_create``, ``bulk_update``) which expect a manager.

## Decision

Adopt **Option A**: three-mode explicit API with the semantics in the
table below.

| Mode | Manager filter | Signals validate | Audit emission |
|------|----------------|------------------|----------------|
| ``Model.objects`` (default) | applies tenant filter | validates coherence | none (normal path) |
| ``Model._unscoped`` | no filter | still validates | none (read-only by design) |
| ``Model._unsafe_unscoped`` (new) | no filter | bypassed | ``ENFORCEMENT_BYPASS`` event |

### Architectural pillars

1. **``_unsafe_unscoped`` MUST emit ``ENFORCEMENT_BYPASS`` on every
   write operation.** Severity ``WARNING``; payload includes the
   caller stack frame, the model qualname, the operation type
   (``create`` / ``update`` / ``delete`` / ``bulk_*``), and the row
   count affected when known. The audit emission is non-optional;
   adopters cannot register a sink configuration that suppresses it.

2. **``_unsafe_unscoped`` is a manager attribute, not solely a context
   manager.** ``Model._unsafe_unscoped.bulk_create([...])`` is the
   canonical shape. The manager attribute composes naturally with
   queryset chaining (``.filter()``, ``.exclude()``) when a partial
   bypass is needed. Context-manager form is a secondary affordance
   layered on top, not the primary one.

3. **``_unscoped`` semantics are unchanged.** Findings #12 and #13
   are documented as contract reinforcements (READ-ONLY by design),
   not regressions. The signal validation on the create/update path
   of ``_unscoped`` is the second line of defense (ADR-0007) and
   stays.

4. **New ``AuditEventType.ENFORCEMENT_BYPASS`` value.** Joins the
   existing six-value enum (``CONTEXT_BOUND`` / ``CONTEXT_RELEASED``
   / ``POLICY_ALLOW`` / ``POLICY_DENY`` / ``ENFORCEMENT_VIOLATION`` /
   ``SINK_FAILURE``) as a seventh, dispatched from the new manager.
   ENFORCEMENT_VIOLATION and ENFORCEMENT_BYPASS are jointly the
   "enforcement boundary events" -- one for cross-tenant violations
   detected, one for explicit bypass exercised.

5. **Adopter call-site whitelist convention.** Recommended adopter
   policy (documented in adapter usage docs and reflected in
   anticipated Counterbook ADR-0025): each ``_unsafe_unscoped`` call
   site is preceded by an inline comment
   ``# ENFORCEMENT_BYPASS: <reason>`` and pinned by a test that
   asserts the audit event was emitted with the expected payload.

## Why other options rejected

- **Option B** leaves Counterbook KG-003 unblocked indefinitely.
  Documentation alone does not provide a legitimate write path;
  the workaround (fake ``tenant_scope``) remains the only available
  pattern.
- **Option C** -- a ``bypass_signals=True`` keyword on existing
  ``_unscoped`` methods -- is per-call configuration. Easier to miss
  in code review than a separate manager attribute, and makes the
  surface "what does ``_unscoped`` do?" harder to answer in one
  sentence.
- **Option D** -- context manager only -- breaks the bulk-operation
  ergonomics that motivate Finding #10. ``bulk_create`` returns
  instances; pairing it with a ``with`` block adds ceremony without
  buying expressiveness.

## Consequences

### Positive

- **Counterbook KG-003 unblocks.** ``Model._unsafe_unscoped.bulk_create([...])``
  replaces the individual-INSERT loop in ``roll_forward_period``,
  removing four sprints of accumulated technical debt.
- **D-CTA.0 architectural foundation.** The dual-dispatch pattern
  established by ``_unsafe_unscoped`` (audit emission alongside the
  enforcement decision) is the same pattern D-CTA.0 will reuse for
  cross-tenant ``.update()`` / ``.delete()`` audit emission (Finding
  #1, SOC2 BLOCKER). Phase 6 trajectory benefits from a single
  pattern applied twice.
- **Findings #12 and #13 resolved via documentation.** ``_unscoped``
  semantics are stable; only the surface (docs) changes.
- **Teachable 3-mode API.** Default / read-only escape / write
  escape. One sentence per mode.

### Negative

- **New public API surface.** ``_unsafe_unscoped`` joins the
  supported contract. It cannot be removed in future minor versions
  without a deprecation cycle.
- **Audit event volume.** Enterprises with frequent admin operations
  emit more ``ENFORCEMENT_BYPASS`` events. Mitigation: events are
  ``WARNING`` severity, not ``ERROR``; adopter SIEM rules can group
  by ``model`` + ``operation`` for noise reduction without losing
  per-event traceability.
- **Bypass is opt-in but visible.** Adopters who do not enforce
  call-site whitelisting risk uncontrolled usage. Mitigation: this
  ADR documents the recommended adopter policy; adapter docs
  (D-DOCS.0) include a worked example.

### Neutral

- **Performance.** ``_unsafe_unscoped`` skips signal validation, so
  it is marginally faster than the scoped path. This is **not**
  marketed as a performance optimization; presenting it as one would
  invite misuse.

## Implementation roadmap

- **D-USU.0 (Phase 6 Day 1, hora 2-4).** Implement
  ``_unsafe_unscoped`` as a manager attribute on
  ``TenantAwareManager``. Signal-bypass mechanism via a context flag
  set inside the manager's queryset (``contextvars.ContextVar`` to
  preserve async semantics, per ADR-0009). Emit ``ENFORCEMENT_BYPASS``
  on every write. Behavioral tests covering ``create`` / ``update``
  / ``delete`` / ``bulk_*`` plus signal-bypass plus audit emission.
  Tag ``v0.5.1-alpha``.
- **D-CTA.0 (Phase 6 Day 2-3).** Cross-tenant ``.update()`` /
  ``.delete()`` audit emission (Finding #1, SOC2 BLOCKER). Reuses the
  ``_unsafe_unscoped`` dual-dispatch pattern but emits
  ``ENFORCEMENT_VIOLATION`` (cross-tenant attempt detected) instead
  of ``ENFORCEMENT_BYPASS`` (intentional bypass exercised). Tag
  ``v0.5.2-alpha``.
- **D-DOCS.0 (Phase 6 Day 5).** Findings #12 and #13 documented as
  contract reinforcements. ``_unsafe_unscoped`` usage guidance added
  to adapter docs with the worked Counterbook
  ``roll_forward_period`` example and the recommended
  whitelist-comment convention.

## Adopter coordination

Counterbook Sprint 5 (Banking) cannot initiate until TenantShield
``v0.5.1-alpha`` is released (D-USU.0 closure). Per the amendment to
ADR-0015 (Counterbook side, 2026-05-20), the pause week was scheduled
**before** Sprint 5 specifically to unblock KG-003 and resolve SOC2
BLOCKER #1 ahead of Banking implementation. Banking on
TenantShield ``v0.6.0a0`` will be architecturally cleaner: it gets a
mature dual-dispatch audit surface and a stable ``_unsafe_unscoped``
contract from day one.

Counterbook ADR-0025 (anticipated, adopter side) will codify usage
policy:

- Explicit whitelist of ``_unsafe_unscoped`` call sites in a
  project-level registry.
- Inline ``# ENFORCEMENT_BYPASS: <reason>`` comment mandatory per
  usage.
- Per-usage test that asserts the audit event was emitted with the
  expected payload shape (caller frame + model + operation + row
  count).

## References

- Finding #1 (SOC2 BLOCKER) -- silent cross-tenant ``.update()`` /
  ``.delete()`` audit gap; resolved by D-CTA.0.
- Finding #10 (HIGH) -- ``_unsafe_unscoped`` API missing; resolved by
  D-USU.0 per this ADR.
- Finding #12 (CONTRACT) -- ``_unscoped.update()`` raises
  ``MissingTenantContextError`` outside ``tenant_scope``; resolved by
  documentation in D-DOCS.0.
- Finding #13 (CONTRACT) -- ``_unscoped.create()`` respects
  ``pre_save`` signal validation; resolved by documentation in
  D-DOCS.0.
- ADR-0007 -- Event-based enforcement for SQLAlchemy adapter
  (orthogonality of manager filter vs signal validation).
- ADR-0011 -- Observability architecture (event taxonomy and
  emission gate).
- ADR-0012 -- Audit-observability dual-pattern (the architectural
  precedent ``_unsafe_unscoped`` extends to a third dispatch site).
- ADR-0015 (Counterbook side) -- TenantShield upstream improvement
  schedule; pre-Sprint-5 pause amendment.
