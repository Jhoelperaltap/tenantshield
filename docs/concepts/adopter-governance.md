# Adopter governance pattern

TenantShield ships **architectural primitives**; adopter codebases
ship **policies that codify how those primitives are used**.
Crystallized empirically across three Counterbook adoption cycles
(Phase 6 ``v0.5.1`` → ``v0.5.3``), this pattern recommends adopters
maintain their own ADR-driven governance layer per TenantShield API
surface.

## The pattern

For each TenantShield opt-in API surface (e.g.,
``_unsafe_unscoped``, ``audit_cross_tenant_attempts``,
``auto_propagate_from_parent_fk``), the adopter writes a local ADR
that documents:

1. **Scope policy** -- which models in the codebase use the
   primitive, and which deliberately do not. Often expressed as a
   tier system (e.g., "Tier 1 financial integrity models MUST
   enable audit; Tier 4 internal-only models MAY skip").
2. **Whitelist / blacklist** -- call sites where the primitive is
   authorised (especially for bypass APIs like ``_unsafe_unscoped``).
   The whitelist exists in code (inline ``# ENFORCEMENT_BYPASS:
   <reason>`` comments) AND in the ADR (audit-reviewable list).
3. **Adopter test convention** -- per-callsite test that pins the
   primitive's behaviour. For bypass APIs: assert the audit event
   is emitted with the expected payload. For audit APIs: pin both
   emission-when-violation AND silence-when-legitimate (inverse
   pinning).
4. **Compliance hook** -- explicit mapping from the primitive to
   the adopter's compliance regime (SOC2 control X, PCI-DSS
   requirement Y), so auditors trace the chain from regulation to
   implementation.

## Why adopter ADRs, not upstream ADRs?

TenantShield upstream ADRs (this codebase) define the **minimum
guaranteed contract** for each API. Adopter ADRs define the **local
deployment policy**. The two layers are complementary:

- Upstream ADR-0013 says: ``_unsafe_unscoped`` exists, emits
  ENFORCEMENT_BYPASS, bypasses signal validation.
- Adopter ADR-0025 (Counterbook example) says: of the 17 models in
  our codebase that could use ``_unsafe_unscoped``, only 2 do, both
  in ``roll_forward_period`` and ``replay_journal``; here is the
  test that pins each call site.

The upstream contract is stable across all adopters; local policy
varies by codebase, compliance regime, and team risk tolerance.
Codifying the policy locally (rather than upstream) keeps
TenantShield architecturally neutral while giving adopters a
documented review trail.

## Example from Counterbook adoption

Counterbook, the Phase 6 reference adopter, maintains:

- **ADR-0025**: ``_unsafe_unscoped`` usage policy. Lists 2
  authorised call sites; bans usage elsewhere; documents the test
  pattern.
- **ADR-0026**: ``audit_cross_tenant_attempts`` 4-tier scope
  policy. 13 financial integrity models + 4 master/config models =
  17 Tier 1+2 models with audit enabled. Tier 3 (operational logs)
  and Tier 4 (caches) skip audit per noise/cost tradeoff.
- **ADR-0027**: ``auto_propagate_from_parent_fk`` governance.
  Documents which 5 child models opt in, with rationale per model
  about the FK parent relationship.

Cross-referencing: each adopter ADR cites the upstream TenantShield
ADR that defines the primitive, so the chain from local policy to
upstream contract is explicit.

## Tests as pinned contracts

The pattern's testing arm is the highest-value piece: per-callsite
tests prevent silent regressions where someone removes a whitelist
entry or enables a bypass on a previously-restricted model. The
test count for governance pinning often exceeds the count of
behavioural tests (Counterbook ADR-0026 alone: 16 tests covering
17 models). This is **intentional asymmetry**: the governance layer
is what auditors review, so it deserves test density.

## Recommended adopter checklist

When adopting a new TenantShield primitive, the adopter SHOULD:

- [ ] Draft a local ADR before broad rollout.
- [ ] Define scope: which models use the primitive, which do not.
- [ ] List call sites explicitly (especially for bypass APIs).
- [ ] Write per-callsite tests pinning the expected behaviour.
- [ ] Document the compliance hook (SOC2 / PCI-DSS / internal).
- [ ] Cross-reference the upstream TenantShield ADR.
- [ ] Re-run pin audit before each TenantShield version bump.

## Cross-references

- ADR-0013 -- Three-mode read/write semantics.
- [Security posture](security-posture.md) -- the layer model the
  governance pattern operates over.
