# ADR-0014 -- Phase 6 retrospective: Track A cohort handover trajectory

**Status:** Accepted.
**Date:** 2026-05-23.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase), Counterbook
adopter Tech Lead (parallel session, Owner-relayed).
**Supersedes:** None.
**Superseded by:** None.
**Related:** ADR-0013 (Three-mode read/write semantics) -- core Phase 6
architectural foundation; Counterbook ADR-0015 (downstream catalog of 13
findings driving Phase 6 trajectory); Counterbook ADR-0025 / 0026 / 0027
(downstream governance ADRs validating Pattern Cluster F adopter
ADR-driven governance pattern).

## Context

Phase 6 was TenantShield's first phase informed empirically by Track A
adopter feedback. Counterbook (Owner's parallel SaaS contable project)
served as the inaugural reference adopter, integrating TenantShield
``v0.5.0a0`` in production-style work and surfacing 13 architectural
findings during Sprints 0-4. The findings were catalogued in
Counterbook's ADR-0015 and handed back to TenantShield for upstream
resolution.

Phase 6 ran for **7 days** (2026-05-17 → 2026-05-23) and produced
**5 incremental releases** (``v0.5.1-alpha`` → ``v0.5.4-alpha``)
plus the Phase 6 root tag ``v0.6.0-alpha``. Across the phase,
**4 Counterbook validation cycles** (#007-KG003, #008-CTA-AUDIT,
#009-AUTO-PROPAGATE, #010 minimal pin bump) empirically ratified the
upstream architectural extensions. By Day 6 closure, all 13 ADR-0015
findings were cleared (12 RESOLVED via implementation + 1 PRE-RESOLVED
via Rule 70 archaeology).

This ADR consolidates the Phase 6 retrospective: the trajectory
summary, the 7 Pattern Clusters that crystallized empirically during
the phase, the 5 Rules (74-78) ratified as project conventions, the
reference adopter acknowledgment, and the lessons-learned for future
phases that scale beyond single-adopter validation.

## Trajectory summary

Five incremental releases on a 7-day cadence, each tied to a
specific Counterbook validation cycle:

| Day | Release | Architectural work | Counterbook cycle | Finding(s) cleared |
|---|---|---|---|---|
| 1 (2026-05-17) | ``v0.5.1-alpha`` | D-MEM.0 + ADR-0013 + D-USU.0 (``_unsafe_unscoped``) | #007-KG003 | #10 (HIGH) |
| 2-3 (2026-05-23) | ``v0.5.2-alpha`` | D-MEM.1 + CI recovery + D-CTA.0 (cross-tenant audit) | #008-CTA-AUDIT | #1 (SOC2 BLOCKER) |
| 4 (2026-05-23) | ``v0.5.3-alpha`` | D-MEM.2 + D-VAL.0 SKIP + D-DX.0 + D-AUTO.0 (FK auto-propagate) | #009-AUTO-PROPAGATE | #2 + #5 + #6 + #11 |
| 5 (2026-05-23) | ``v0.5.4-alpha`` | D-MEM.3 + D-PERF.0 + D-PY314.0 + D-DOCS.0 | #010 (saturation) | #7 + #8 + #9 + #12 + #13 |
| 6 (2026-05-23) | (NO TAG, consolidated) | D-MEM.4 + D-NEST.0 SKIP + D-MIG.0 + D-ADM.0 | (deferred to Day 7) | #3 + #4 |
| 7 (2026-05-23) | **``v0.6.0-alpha``** (this) | D-MEM.5 + D-DIST.0 + Item-26 defer + ADR-0014 + CHANGELOG | (anticipated #011 post-tag) | -- closure -- |

The "Day" numbering refers to architectural work cadence, not
calendar days; Days 2-7 all closed on 2026-05-23 because the trajectory
ran faster than the planned 7-day calendar window.

## The 7 Pattern Clusters

Empirically crystallized across the phase. Each cluster emerged from
multiple specific instances; the abstraction is documented here for
future-phase reference and adopter guidance.

### Cluster A -- "3-mode read/write semantics + Triple-layer defense"

Foundation: ADR-0013 codified ``Model.objects`` (mode 1) + ``_unscoped``
(mode 2) + ``_unsafe_unscoped`` (mode 3) as the canonical access
contract for ``@tenant_aware`` models. Empirically refined into a
triple-layer defense model (see ``docs/concepts/security-posture.md``):

- Layer 1: Manager scope filtering (passive).
- Layer 2: ``audit_cross_tenant_attempts=True`` (soft-audit, D-CTA.0).
- Layer 3: ``auto_propagate_from_parent_fk=True`` (HARD REJECT,
  D-AUTO.0; empirically surfaced by Counterbook #009 -- NOT in
  ADR-0013 spec).

The Counterbook #009 validation discovered that D-AUTO.0 + the
existing validator chain delivers a HARD REJECT on cross-tenant FK
attempts before the INSERT executes -- a stronger guarantee than
ADR-0013 anticipated. The triple-layer composition is the
empirically-validated security posture documented in Phase 6 docs.

### Cluster B -- "Silent → Observable"

Findings #1 (SOC2 BLOCKER) + #5 (startup validation) + #8
(``pre_save`` performance overhead) shared the theme that enterprise
compliance posture requires observable behaviour, not silent
correctness. Pre-Phase-6 ``v0.5.0-alpha`` was correct (cross-tenant
writes returned 0 rows) but silent (no audit, no exception). Phase 6
elevated each silent failure mode into an observable signal: audit
events (D-CTA.0), startup checks (#5 PRE-RESOLVED via Phase 2
infrastructure E001..W002), benchmark pins (D-PERF.0). The cluster's
operational consequence: SIEM tooling can now detect what was
previously invisible.

### Cluster C -- "DX sugar over primitives"

Findings #2 + #6 + #11 shared the theme that adopter ergonomics is
not the same as architectural correctness. The Phase 5 API was
correct; Phase 6 D-DX.0 + D-AUTO.0 layered ergonomic surfaces on top
without sacrificing safety:

- ``MissingTenantContextError`` now includes a canonical pattern hint.
- ``tenant_scope_for_company(company)`` takes a Django instance
  directly (Counterbook adopted in 106 callsites).
- ``@tenant_aware(auto_propagate_from_parent_fk=True)`` eliminates
  the ``child.company = parent.company`` boilerplate pattern.

### Cluster D -- "Django integration polish"

Findings #3 + #4 + #7 + #9 shared the theme of first-class Django
ecosystem citizenship vs parallel system. Phase 6 D-MIG.0 + D-ADM.0
+ D-DOCS.0 closed the gaps:

- ``tenantshield.adapters.django.migrations`` exposes inspection
  helpers for ``@tenant_aware`` model metadata (Finding #3).
- ``TenantAwareAdmin`` mixin auto-includes the tenant filter in
  Django admin (Finding #4).
- ``select_for_update`` interaction + nested ``tenant_scope``
  semantics + ``_unscoped`` contract documented in concept docs
  (Findings #7 + #9 + #12 + #13).

### Cluster E -- "Cross-session coordination protocol"

Phase 6 operated under a tri-session model:

- TenantShield Tech Lead session (this codebase's planning context).
- Counterbook Tech Lead session (parallel adopter's planning).
- Executor session (this codebase's IC work).

The Owner served as coordinator, relaying state between sessions.
4 consecutive validation cycles operated without friction; the
protocol is empirically reproducible. Documented as Item-25 in Phase
6 backlog and codified here:

1. **Upstream emits** an architectural extension (e.g., D-USU.0).
2. **Tag pushed**, release notes prepared.
3. **Owner relays** trigger message to adopter session.
4. **Adopter executes** integration (per their ADR-driven governance).
5. **Adopter approves** with empirical validation report.
6. **Owner relays** approval back upstream.
7. **Upstream proceeds** to next architectural extension.

The model scales for small-N cohorts. Track B / C onboarding may
surface coordination protocol limits and motivate Phase 7 work.

### Cluster F -- "Adopter ADR-driven governance per API surface"

(Note: not a separate enumerated cluster in the Phase 6 emergence
order; folded into Cluster C / E in documentation -- listed here for
completeness as the Counterbook ADR-0025 / 0026 / 0027 pattern.)
Adopter codebases SHOULD maintain local ADRs that codify usage
policy per TenantShield API surface. Counterbook's ADR-0025
(``_unsafe_unscoped`` whitelist) + ADR-0026 (audit scope policy) +
ADR-0027 (auto-propagation governance) became the canonical example.
Documented in ``docs/concepts/adopter-governance.md`` (Phase 6 Day
5). Empirically validated across 4 cycles.

### Cluster G -- "Adopter empirical exploration reveals stronger guarantees than spec" + saturation indicator

The three D-* tareas that shipped architectural extensions (D-USU.0,
D-CTA.0, D-AUTO.0) all surfaced empirical value beyond the spec:

- D-USU.0 + Counterbook #007: >10x bulk-create perf gain
  (architectural unblock + perf gain combined value).
- D-CTA.0 + Counterbook #008: auditor-grade ``caller_stack_frames``
  forensics (SOC2/PCI-DSS posture stronger than spec described).
- D-AUTO.0 + Counterbook #009: HARD REJECT security posture (NOT in
  ADR-0013 spec).

Counterbook #010 (the v0.5.4-alpha pin bump) surfaced ZERO new
architectural insights -- a **saturation indicator**. The 3-cycle
pattern of "insights beyond spec" gave way to a single-commit pin
bump with no new architectural learning. Empirical lesson: future
multi-cohort onboarding can use the cycle count of "no new insights"
as an API stability metric per cohort.

### Cluster H -- "Empirical pragmatism trumps rigid procedural ideals"

Two empirical observations stacked into a single cluster:

- **Day 5 (D-PERF.0)**: empirical archaeology revealed Django
  signals are per-sender; non-tenant-aware models incur zero handler
  overhead. The expected optimization (early-return shortcut) was
  unnecessary because the existing architecture (signal dispatch +
  ``_signal_bypass_var``) was already efficient. Pattern: measure
  empirical baseline BEFORE designing an optimization.

- **Day 6 (D-MIG.0 + D-ADM.0)**: the spec called for two atomic
  commits; the empirical reality was that the two findings shared
  ``__init__.py`` exports that couldn't be cleanly split without
  artificial intermediate states. Tech Lead acknowledged Option β
  (combined commit) as valid. Pattern: commit atomicity should
  respect file-level cohesion when forced splits create artifacts.

The umbrella theme: rigid procedural ideals (single-finding
per-commit, optimize-before-measuring) yield to empirical pragmatism
when the procedural cost exceeds the architectural value.

## Rules 74-78 ratified

Rules 74-78 are added to the project rule catalog (Rules 1-73 from
prior phases unchanged). Each derives from a specific Pattern
Cluster crystallization.

- **Rule 74** -- *Per-operation aggregation in dual-dispatch audit
  emission*. When an audit emit fires on a bulk operation (N rows),
  emit ONE event with N PKs in the payload, NOT N events. Derived
  from D-CTA.0 empirical adoption (Counterbook #008).

- **Rule 75** -- *Inverse pinning test convention*. Behavioural tests
  for opt-in audit / detection APIs MUST validate BOTH directions:
  emission-when-violation AND silence-when-legitimate. Derived from
  Counterbook IC architectural judgment during #008 integration.

- **Rule 76** -- *Adopter ADR-driven governance per API surface*.
  Each TenantShield opt-in primitive (``_unsafe_unscoped``,
  ``audit_cross_tenant_attempts``, ``auto_propagate_from_parent_fk``)
  SHOULD be paired with a local adopter ADR codifying scope policy,
  whitelist / blacklist, test convention, and compliance hook.
  Derived from Counterbook ADR-0025 / 0026 / 0027 pattern.

- **Rule 77** -- *Cohort handover surfaces architectural value beyond
  spec author capacity*. Spec architectural extensions as "minimum
  guaranteed contract" with documentation hooks for empirical
  enrichment from adopter integration. Derived from Pattern Cluster
  G across 3 consecutive validation cycles.

- **Rule 78** -- *Empirical baseline + pragmatic atomicity*. (a)
  Architectural performance work MUST establish empirical baseline
  before designing an optimization. (b) Commit atomicity should
  respect file-level cohesion when interleaved changes prevent a
  clean split. Derived from Pattern Cluster H (Day 5 archaeology +
  Day 6 combined commit).

## Reference adopter acknowledgment

Counterbook (Owner's parallel SaaS contable project, integrating
TenantShield since ``v0.5.0a0``) served as Phase 6's **reference
adopter**. Counterbook's contributions across the phase:

- **13 findings catalogued** (ADR-0015), driving the entire Phase 6
  trajectory.
- **4 mini-tickets executed** (#007-KG003, #008-CTA-AUDIT,
  #009-AUTO-PROPAGATE, #010) empirically validating each upstream
  release.
- **3 adopter ADRs** (Counterbook ADR-0025 + ADR-0026 + ADR-0027)
  codifying local governance policy and serving as the canonical
  example of Cluster F.
- **Empirical architectural discoveries beyond spec**: >10x
  bulk-create perf gain (D-USU.0), HARD REJECT security posture
  (D-AUTO.0), saturation indicator (#010).
- **Reference adopter status formalized** post-#010 (Phase 6 Day 5).

TenantShield's Phase 6 architectural maturity is, empirically, the
result of Counterbook's adoption pressure. Cluster G is the structured
acknowledgment of that asymmetric value flow.

## Lessons learned (cross-project)

- **Owner-as-coordinator scales for small-N cohorts**. The tri-session
  protocol works fluently with one adopter. Track B / C onboarding
  is the empirical test of where the model strains.
- **Empirical-first discipline pays dividends compound**. The
  71-tarea empirical-first streak sustained through Phase 6 reflects
  a protocol that, once internalised, costs less than alternatives.
  Rule 70 archaeology saved D-VAL.0 + D-NEST.0 + (partially) D-PERF.0
  -- each a tarea that would have been built before being verified
  unnecessary.
- **DR-004 enforcement protocol** (no AI attribution in commit
  messages) operated mandatory per-GO across the full phase. The
  invariant held: every commit + tag + memory file emerged clean.
  The discipline cost is small once the self-check pattern is
  reflexive.
- **Memory refresh cadence per phase boundary** (D-MEM.0..5 +
  prior D-MEM.* in earlier phases) preserves cross-conversation
  continuity. The B' / B'' / B''' / B'''' incremental naming
  convention extended naturally without requiring section
  re-numbering.

## Phase 7+ trajectory anticipated

The Phase 6 closure unblocks several Phase 7 trajectories. None of
them is yet ratified; this section documents anticipated work for
Owner discretion.

- **Multi-adopter cohort scaling**. Track B / C onboarding will test
  the Cluster E coordination protocol limits. Specific scaling
  primitives (issue templates, response SLA conventions, automated
  pin-bump verification) may emerge as Phase 7 deliverables.
- **PyPI public publish**. The Phase 6 D-DIST.0 TestPyPI workflow is
  the staging surface; the migration to public PyPI (``pip install
  tenantshield`` from the default index) is a Phase 7 decision
  awaiting broader cohort feedback signal.
- **Production performance optimization based on adopter data**. The
  Cluster H Day 5 finding -- that the Django signal chain is
  inherently efficient -- generalises to other code paths only if
  adopter telemetry confirms. Phase 7 may receive observability
  data from cohort production deployments and surface optimization
  opportunities.
- **Cross-adapter parity audit**. The SQLAlchemy adapter (Phases
  3-5) and Django adapter (Phases 2, 6) have evolved at different
  cadences. A Phase 7 parity audit may surface API surface
  divergences worth normalising.

## Closure

Phase 6 closes with all 13 ADR-0015 findings cleared, 5 incremental
releases shipped, the reference adopter (Counterbook) producing 4
empirically-validated integration cycles, and 7 Pattern Clusters +
5 Rules added to the project's architectural vocabulary. Tag
``v0.6.0-alpha`` marks the milestone. ``__version__`` advances from
``0.5.4a0`` to ``0.6.0a0`` per Rule 49 P1 (5th canonical Phase root
application).
