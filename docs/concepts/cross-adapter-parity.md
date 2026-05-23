# Cross-Adapter Parity Matrix

This document tracks the architectural parity between TenantShield's
adapter implementations. Maintained via periodic empirical
cross-adapter audits (the `D-AUDIT-*-PARITY` task pattern) as new
architectural extensions ship and new adapters are added.

The matrix is canonical: when the parity status diverges (an
extension ships in one adapter but not another), this document is
the single source of truth for the gap categorisation and the
Phase 7+ trajectory.

## Adapters

TenantShield currently supports two production adapters:

- **Django adapter** — Reference implementation, validated by
  Counterbook (Track A cohort, 5 validation cycles, Phase 6).
- **SQLAlchemy (SA) adapter** — Mature implementation, internal
  validation only (no Track A cohort).

Both adapters share the core infrastructure: ``tenant_scope`` /
``bind_tenant`` context API, ``AuditEventType`` enum, exception
hierarchy, and the registry. Divergence is concentrated at the
ORM-binding layer.

## Phase 6 Extensions Parity (Django cohort-driven)

The Phase 6 architectural extensions emerged from Django-cohort
feedback (Counterbook). The SA adapter does not have a Track A cohort
yet; the table below shows where the Phase 6 work has not yet been
ported.

| Extension | Django | SQLAlchemy | Notes |
|---|---|---|---|
| ``_unsafe_unscoped`` manager (D-USU.0) | ✅ Operational | ❌ Missing — item 31 Phase 7 candidate (SA-USU.0) | Different mechanism: SA uses unbound ``Session`` as the documented bypass pattern |
| ``ENFORCEMENT_BYPASS`` audit event | ✅ Emitted (D-USU.0) | ❌ Missing — tied to item 31 | Will follow SA-USU.0 work |
| ``audit_cross_tenant_attempts`` flag (D-CTA.0) | ✅ Optional soft-audit | ⚠️ Equivalent via events (always-on hard-raise) | SA architectural strength: pre-SQL raise since Sub-fase 3A |
| ``auto_propagate_from_parent_fk`` (D-AUTO.0) | ✅ Operational (HARD REJECT) | ❌ Missing — item 32 Phase 7 candidate (SA-AUTO.0) | SA equivalent would inspect SA ``relationship()`` declarations in ``before_insert`` handler |
| ``tenant_scope_for_company()`` shortcut (D-DX.0) | ✅ Operational | ❌ Missing — v0.6.1-alpha hotfix candidate | SA equivalent: ``tenant_scope_for_model(instance)`` reading ``instance.tenant_id`` |
| Migration metadata helpers (D-MIG.0) | ✅ Operational | ❌ Missing — v0.6.1-alpha hotfix candidate | SA equivalent: introspect ``__tenantshield_tenant_aware__`` sentinel |
| ``MissingTenantContextError`` canonical hint (D-DX.0) | ✅ Operational | ✅ Inherited via core | Shared exception class |
| Django admin mixin (D-ADM.0) | ✅ Operational | ❌ N/A | Django admin is framework-specific; no SA equivalent surface |

## Sub-fase 5B.5.1 Foundation (shared)

Both adapters share the audit dual-dispatch infrastructure
introduced in Sub-fase 5B.5.1:

| Foundation Element | Django | SQLAlchemy | Empirical evidence |
|---|---|---|---|
| Audit dual-dispatch helper | ✅ | ✅ | ``adapters/sqlalchemy/events.py:74`` ``_emit_enforcement_violation_audit`` |
| ``ENFORCEMENT_VIOLATION`` emission | ✅ | ✅ | ``adapters/sqlalchemy/events.py:97`` |
| ``AuditEvent`` import + usage | ✅ | ✅ | Shared core |
| Tenant-aware sentinel | ✅ | ✅ | ``__tenantshield_tenant_aware__`` |
| ``MissingTenantContextError`` raise on missing scope | ✅ | ✅ | SA: ``events.py:140`` / ``216`` / ``298`` |
| ``CrossTenantAccessError`` raise on cross-tenant attempt | ✅ (via D-CTA.0 pre-flight) | ✅ (via event listener, since Sub-fase 3A) | SA: 5 raise sites in ``events.py`` |

## SQLAlchemy Architectural Strengths

The SA adapter has architectural properties that the Django adapter
achieves only through retrofitted Phase 6 work:

**Pre-SQL Enforcement.** SA's ``before_*`` event listeners fire
before SQL executes. Cross-tenant ``.update()`` / ``.delete()``
attempts raise ``CrossTenantAccessError`` and emit
``ENFORCEMENT_VIOLATION`` — *the SQL never reaches the database*.

The Django adapter required Phase 6 D-CTA.0 to retrofit pre-flight
detection (via ``.update()/.delete()`` interception). The SA adapter
has had this property since Sub-fase 3A via the event-based
enforcement model documented in ADR-0007.

The architectural consequence: for adopters whose threat model is
"any cross-tenant attempt must be observable AND blocked", SA
delivers the strongest default. For adopters whose threat model
tolerates silent zero-row outcomes and wants the option of audit-
only soft-mode, Django D-CTA.0's configurable opt-in fits better.
Neither is universally superior; the adapter choice should follow
the application's ORM choice and the security-posture matrix.

## Phase 7 Candidates (deferred)

The following architectural extensions are catalogued for Phase 7
work, typically driven by SA cohort onboarding signal:

### Item 31 — SA-USU.0

`_unsafe_unscoped` equivalent for SQLAlchemy + `ENFORCEMENT_BYPASS`
SA emission. Estimated effort: ~3-5 hours architectural work + 8-12
behavioural tests.

**Pre-requisite**: an `ENFORCEMENT_BYPASS` emission site SA-side, so
the audit stream symmetrically covers Django bypass + SA bypass.

**Design sketch**: introduce a ``unsafe_unscoped_session()`` context
manager (or similar) that yields an ``Session`` with a contextvars
flag set; the SA event listeners check the flag and short-circuit
on ``True`` while emitting ``ENFORCEMENT_BYPASS`` for the operation.

Status: deferred until SA cohort signal (Track B/C onboarding OR
explicit SA-adopter request).

### Item 32 — SA-AUTO.0

SA equivalent of `auto_propagate_from_parent_fk`. Estimated effort:
~3-4 hours + 6-8 tests.

**Design sketch**: extend the ``before_insert`` handler to inspect
SA ``relationship()`` declarations on the model, find the parent
relationship target, copy the parent's ``tenant_id`` to the child if
the child's ``tenant_id`` is unset.

Status: deferred until SA cohort signal.

### Item 33 — SA `audit_cross_tenant_attempts` soft-mode

LOW priority. The SA adapter already enforces cross-tenant detection
as hard-raise (always-on). Adding an optional soft-audit mode would
match Django D-CTA.0 configurability but provides little practical
value over the existing hard-mode (SA's hard-mode is architecturally
stronger). Estimated effort: ~1-2 hours + 4-5 tests.

Status: deferred indefinitely unless an adopter empirical use case
emerges.

## Audit Methodology

This matrix is maintained via periodic empirical cross-adapter
audits (`D-AUDIT-*-PARITY` task pattern). Audits inspect:

1. Phase X extensions present in audited adapter.
2. Categorisation: cross-cutting / adapter-specific / trivial / docs.
3. Counter-findings (audited adapter strengths that the reference
   adapter lacks).
4. Phase 7+ candidates surfaced.

Audits are **read-only**: no code is modified during the audit task.
The output is a categorised report that feeds the Phase 7+ backlog.

The methodology is grounded in Pattern Cluster G (see ADR-0014),
which the Phase 6 retrospective documents as the canonical pattern
for empirical architectural value discovery. The reactive arm of
Pattern Cluster G (adopter feedback) and the proactive arm
(cross-adapter audit) compose to give full architectural integrity
validation across both adopter perspectives and adapter
implementations.

## Maintenance

Update this document when:

- A new architectural extension ships (add a row to the Phase 6 / 7 /
  N table).
- An audit is performed (update the corresponding gap row + Phase 7
  candidate list).
- A Phase 7 candidate is implemented (move it out of the candidate
  section into the parity table with ✅).
- A new adapter is added (add a column to all tables).

## References

- **ADR-0013** -- Three-mode read/write semantics (Django Phase 6
  foundation).
- **ADR-0014** -- Phase 6 retrospective (Pattern Cluster G + Rule 77
  ratification).
- **ADR-0015** -- Counterbook handover findings (13/13 cleared Phase
  6); referenced from this document for the source of Phase 6
  cohort-driven extensions.
- **D-AUDIT-SA-PARITY** (2026-05-23): post-Phase-6 cross-adapter
  audit that produced this matrix.
- [Security posture](security-posture.md) -- per-adapter architectural
  defense model.
