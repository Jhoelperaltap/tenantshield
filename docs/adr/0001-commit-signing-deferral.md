# ADR 0001 — Commit signing deferral

**Status:** Accepted
**Date:** 2026-05-13 (originally as DR-003); formalized as ADR 2026-05-14.
**Decision-makers:** Project owner.

## Context

Modern open source projects increasingly require signed commits (GPG, SSH,
or Sigstore) to:

- Prove authorship of contributions.
- Detect tampering with the commit history.
- Comply with supply-chain attestation frameworks (SLSA, sigstore).

GitHub displays a "verified" badge on signed commits. Some downstream
distributors (Fedora, conda-forge) prefer signed releases.

TenantShield is a pre-1.0 project under active development by a single
owner. Signing every commit during prototyping adds friction without
proportional security benefit: there is no contributor diversity yet,
and the cost of a wrong signature (forgotten key, machine swap, CI signing
config) interrupts iteration.

## Decision

**Commits are not signed until immediately before the `v0.5.0-alpha`
release tag.**

- Phase 0 through Phase 5 development happens with unsigned commits.
- Before tagging `v0.5.0-alpha`, the owner configures their signing key
  locally (GPG, SSH, or Sigstore — owner's choice).
- All subsequent commits are signed.
- Pre-`v0.5.0-alpha` commits are NOT rewritten retroactively. Their
  history stays unsigned. The git log will show an inflection point at
  the `v0.5.0-alpha` tag.

## Consequences

**Positive:**

- Zero ceremony during phases 0-5 (rapid iteration with no signing
  config to maintain).
- The signing transition is a single, deliberate change rather than a
  policy retrofitted under pressure.
- Forces explicit configuration of signing keys before the project
  reaches a maturity that warrants attestation.

**Negative:**

- The pre-`v0.5.0-alpha` history cannot be cryptographically verified.
  Anyone auditing the history must trust the GitHub authentication
  layer alone for those commits.
- Some users may prefer signed history from day one; they will be
  disappointed during phases 0-5.

**Mitigations:**

- The project's `CONTRIBUTING.md` documents this decision so contributors
  understand the timeline.
- This ADR is the canonical reference; CHANGELOG points to it.

## Alternatives considered

**Sign from commit zero.** Rejected: adds friction during phases where
the API and toolchain are still settling, increases probability of
configuration errors during fast iteration.

**Sign starting at `v1.0.0`.** Rejected: `v1.0.0` is too late. Phase 5
(Query Analyzer) introduces an analyzer that other projects may consume;
its release deserves attestation.

**Retroactively sign all commits at `v0.5.0-alpha`.** Rejected: rewriting
git history breaks any forks, mirrors, or backups. The inflection point
is cleaner.

## References

- `CHANGELOG.md` Decision Records, DR-003.
- Roadmap §6 #10.
