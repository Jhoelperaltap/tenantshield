# Security posture

TenantShield delivers cross-tenant isolation through **three layers of
defense**, stacked opt-in per model. Each layer addresses a different
class of failure mode, with progressively stronger guarantees at the
cost of additional infrastructure.

This page documents the triple-layer model empirically validated
across three Counterbook adopter cycles (Phase 6, ``v0.5.1`` →
``v0.5.3``). The model emerged from cohort feedback; the layers are
documented here as the **minimum guaranteed architectural contract**
rather than a feature inventory.

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

## References

- ADR-0013 -- Three-mode read/write semantics for ``@tenant_aware`` models.
- ADR-0007 -- Event-based enforcement for SQLAlchemy adapter.
- ADR-0011 -- Observability architecture (audit event taxonomy).
- ADR-0012 -- Audit-observability dual-pattern.
