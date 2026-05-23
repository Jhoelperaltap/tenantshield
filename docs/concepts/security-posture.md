# Security posture

TenantShield delivers cross-tenant isolation through adapter-specific
mechanisms. The Django adapter uses a **three-layer opt-in defense
model** (documented below). The SQLAlchemy adapter uses a single
always-on **event-based pre-SQL enforcement** mechanism with stronger
default behaviour (see [SQLAlchemy section](#sqlalchemy-adapter-security-posture)
at the bottom of this page). Adopters select the adapter matching
their ORM; the cross-tenant guarantees differ in shape but converge
on the same outcome: cross-tenant data does not leak.

This page documents the Django triple-layer model empirically
validated across three Counterbook adopter cycles (Phase 6, ``v0.5.1``
→ ``v0.5.3``). The model emerged from cohort feedback; the layers are
documented here as the **minimum guaranteed architectural contract**
rather than a feature inventory.

## Django Adapter Security Posture

The Django adapter exposes three layers of defense, stacked opt-in
per model. Each layer addresses a different class of failure mode,
with progressively stronger guarantees at the cost of additional
infrastructure.

## Layer 1 -- Manager scope filtering (always on)

The default ``Model.objects`` manager rewrites every read to
``WHERE tenant_id = <ctx>`` at queryset construction. Cross-tenant
reads return zero rows; cross-tenant writes via the ORM happen in a
queryset that is already filtered. This is the **passive** layer:
adopters get isolation by default, without opt-in.

Failure mode addressed: forgotten ``.filter(tenant_id=...)`` calls.
The layer makes scoping the default, not an opt-in convention.

## Layer 2 -- ``audit_cross_tenant_attempts`` (soft-audit, opt-in)

When ``@tenant_aware(audit_cross_tenant_attempts=True)`` is set,
``Model.objects.filter(...).update(...)`` and ``.delete()`` perform a
pre-flight unscoped query that detects PKs matching the caller's
other filters but belonging to OTHER tenants. Each such attempt
emits ``ENFORCEMENT_VIOLATION`` with the attempted PKs + caller
stack frames.

Failure mode addressed: silent zero-row writes that bypass detection
under the default manager. Without this layer, a probing actor
iterating PKs leaves no forensic trail (0 rows affected, no
exception). With this layer, every cross-tenant probe generates a
SIEM-detectable event.

This is the **soft-audit** layer: writes still fail (Layer 1 still
filters), but now the attempt is observable. OFF by default for
adopter noise management; enable for SOC2 Type II / PCI-DSS posture.

## Layer 3 -- ``auto_propagate_from_parent_fk`` (HARD REJECT, opt-in)

When ``@tenant_aware(auto_propagate_from_parent_fk=True)`` is set on
a child model whose FK points to another tenant-aware parent, the
``pre_save`` chain auto-populates the child's ``tenant_field`` from
the parent. Empirically discovered architectural value (Counterbook
``v0.5.3`` adoption, not in original ADR-0013 spec):

**If the FK parent belongs to a different tenant than the active
scope, ``CrossTenantAccessError`` is raised BEFORE the INSERT
executes.** No row is inserted, no audit event is emitted; the
operation aborts in the validator chain.

Failure mode addressed: ``child.tenant_id = parent.tenant_id``
boilerplate combined with implicit assumption that scope == parent.
Without this layer, a malicious or buggy caller could attach a child
record to a foreign-tenant parent while operating in their own
tenant scope, and the validator chain (auto-filling from active
scope) would silently fix up the inconsistency. With this layer, the
mismatch surfaces as a hard error.

This is the **HARD REJECT** layer. Stronger than Layer 2: not
just observable, but blocking at the validator level before SQL
runs.

## Choosing layers

| Posture | Layers enabled | Use case |
|---------|----------------|----------|
| Default (no flags) | 1 | Internal apps, low compliance burden, small adopter teams |
| Compliance-aware | 1 + 2 | Apps with audit/SOC2/PCI-DSS requirements; tolerate audit volume |
| Defense-in-depth | 1 + 2 + 3 | Financial / healthcare / multi-tenant SaaS; FK-rich domain models |

The layers compose orthogonally: enabling Layer 3 does not affect
Layer 2 behaviour, and vice versa. Adopters can adopt layers
incrementally per model.

## Interaction with ``_unsafe_unscoped`` (mode 3)

``Model._unsafe_unscoped`` writes bypass the entire ``pre_save``
chain by setting ``_signal_bypass_var``. This means all three
layers are temporarily off for that write path. Adopters MUST set
``tenant_field`` explicitly when using ``_unsafe_unscoped``, and
SHOULD whitelist the call sites via the ``# ENFORCEMENT_BYPASS:
<reason>`` comment convention.

See [ADR-0013 §Mode 3 supplement](../adr/0013-three-mode-read-write-semantics.md#mode-3-supplement-interaction-with-auto_propagate_from_parent_fk)
for the full interaction model.

## SQLAlchemy Adapter Security Posture

The SQLAlchemy adapter takes a different architectural approach to
cross-tenant enforcement than the Django adapter's opt-in layer model.
The SA adapter uses **always-on event-based pre-SQL enforcement** as
the single mechanism.

### Event-based Pre-SQL Enforcement

The SA adapter registers Core event listeners (``before_insert``,
``before_update``, ``before_delete``) on every ``@tenant_aware`` model.
Before any INSERT/UPDATE/DELETE statement reaches the database, the
handler inspects the operation against the active tenant scope. On
cross-tenant detection the handler:

1. Emits an ``ENFORCEMENT_VIOLATION`` audit event with model qualname
   + attempted tenant id + operation label (the Sub-fase 5B.5.1
   dual-dispatch helper ``_emit_enforcement_violation_audit`` lives
   at ``adapters/sqlalchemy/events.py:74``).
2. Raises ``CrossTenantAccessError`` — the SQL statement never
   executes.

The same pattern protects the missing-tenant-context path:
``MissingTenantContextError`` is raised when an INSERT/UPDATE/DELETE
is attempted without an active ``tenant_scope`` (3 raise sites at
``events.py:140``, ``216``, ``298``).

**Empirical totals** (from D-AUDIT-SA-PARITY, 2026-05-23): SA event
listeners raise from 8 sites in ``events.py`` (5 ``CrossTenantAccessError``
+ 3 ``MissingTenantContextError``). The single ``ENFORCEMENT_VIOLATION``
audit emit at ``events.py:97`` fires from every cross-tenant raise
site via the dual-dispatch helper.

### Architectural Property: Fail-Loud, Pre-Flight

Because enforcement runs *before* the SQL executes, there is no
silent zero-row outcome to detect after the fact. The Django adapter
pre-Phase-6 had to handle the silent ``UPDATE WHERE tenant_id = X AND
pk = N`` returning zero rows; Phase 6 D-CTA.0 retrofitted pre-flight
detection. The SA adapter has had this property since Sub-fase 3A.

The architectural consequence: for adopters whose threat model is
"any cross-tenant attempt must be observable AND blocked", the SA
adapter delivers the strongest default. For adopters whose threat
model is "I want soft-audit on the same model the QuerySet might
deliberately reach zero rows for", the Django D-CTA.0 opt-in
soft-mode is the right tool.

### Comparison Summary

| Concern | Django (Phase 6) | SQLAlchemy |
|---|---|---|
| Cross-tenant ``.update()/.delete()`` | Detected via D-CTA.0 pre-flight (opt-in soft-audit) | Raises ``CrossTenantAccessError`` + emits ``ENFORCEMENT_VIOLATION`` (always; not configurable) |
| Detection threat model | Soft-audit OR hard-raise (configurable per model) | Always hard-raise |
| Detection vintage | Phase 6 retrofit (Day 2-3) | Sub-fase 3A native |
| Bypass for legitimate admin writes | ``Model._unsafe_unscoped`` (D-USU.0) with mandatory ``ENFORCEMENT_BYPASS`` audit | NOT YET available; Phase 7 candidate (item 31 SA-USU.0) |

### Audit Event Stream

The SA adapter emits these audit events through the shared
``AuditEventType`` enum:

- ``ENFORCEMENT_VIOLATION`` — emitted when a cross-tenant operation
  is intercepted at the event listener.
- ``CONTEXT_BOUND`` / ``CONTEXT_RELEASED`` — emitted by the core
  ``tenant_scope`` context manager (shared with Django).
- ``POLICY_ALLOW`` / ``POLICY_DENY`` — emitted by the core policy
  evaluator (shared with Django).

The ``ENFORCEMENT_BYPASS`` event is currently emitted only from the
Django ``_unsafe_unscoped`` path (D-USU.0). The SA equivalent
(``SA-USU.0``) is catalogued as Phase 7 candidate item 31; until it
ships, SA adopters whose threat model requires an explicit "bypass
authorised" event must implement the workaround documented in the
[Cross-Adapter Parity Matrix](cross-adapter-parity.md).

### Interaction with Unscoped Sessions

The SA adapter does **not currently expose** an ``_unsafe_unscoped``
equivalent (catalogued as Phase 7 candidate, item 31). Adopters who
need to bypass tenant scoping for legitimate operations (e.g., admin
migrations, system bootstrap, background jobs without tenant context)
must use an explicit ``Session`` instance that was *not* bound via
``bind_session_to_tenant()``. Such a Session does not have the tenant
scope ``ContextVar`` set, so the event listeners observe no active
scope and the auto-fill path at ``before_insert`` populates the
``tenant_id`` from the instance value (or raises
``MissingTenantContextError`` if neither the Session nor the instance
carries a tenant).

This pattern is more verbose than the Django ``_unsafe_unscoped``
manager attribute. The Phase 7 SA-USU.0 work will introduce a more
ergonomic SA-side bypass surface; until then the explicit-unbound-
Session pattern is the documented escape hatch.

## References

- ADR-0013 -- Three-mode read/write semantics for ``@tenant_aware`` models.
- ADR-0007 -- Event-based enforcement for SQLAlchemy adapter.
- ADR-0011 -- Observability architecture (audit event taxonomy).
- ADR-0012 -- Audit-observability dual-pattern.
- ADR-0014 -- Phase 6 retrospective (Pattern Cluster G).
- [Cross-Adapter Parity Matrix](cross-adapter-parity.md) -- audit
  methodology + Phase 7 candidates.
