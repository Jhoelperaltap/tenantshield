# ADR-0005 -- Tight upper bounds for typed-Django ecosystem pins violating Rule 32

**Status:** Accepted.
**Date:** 2026-05-15.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.
**Related:** ADR-0003 (Django 4.2 empirical-CI), ADR-0004 (drf-stubs
empirical-CI), Rule 32 (sec 6 num 32: greater than or equal to 2 weeks
for new dependencies).

## Context

Roadmap sec 6 Rule 32 requires that newly adopted or version-bumped
dependencies have been released for greater than or equal to 14 days
at the moment of adoption. Purpose: filter out releases that may have
undiscovered breaking changes or critical bugs not yet found by
community testing.

During Sub-fase 2C Block C (Django 6.0 matrix expansion), empirical
PyPI verification revealed that current latest stables of both Django
and django-stubs do NOT cumple Rule 32:

- Django 6.0.5 released 2026-05-05 (10 days at decision date).
- django-stubs 6.0.4 released 2026-05-09 (6 days at decision date).

Pin proposals using loose upper bounds (e.g., ``django>=4.2,<7.0``)
would have uv resolve to these latest stables, violating Rule 32.

The typeddjango ecosystem (django-stubs, drf-stubs, Django itself)
releases frequently -- typically monthly cadence. New patches arrive
within Rule 32's 14-day window with high probability when widening
pin ranges. This pattern occurred 3+ times in Sub-fase 2C alone
(drf-stubs 3.16.9 vs 3.17.0 in ADR-0004; Django + django-stubs latest
in this ADR).

ADR-0004 worked by opportunistic transitive conflict: drf-stubs 3.17.0
required django-stubs>=6.0.4 which conflicted with then-current pin
django-stubs<6.0, causing uv to naturally resolve to drf-stubs 3.16.9
(45 days old, cumple Rule 32). This was lucky, not strategic.

For Django + django-stubs in Block C: no transitive conflict prevents
latest from resolving. The opportunistic strategy of ADR-0004 does
NOT apply.

## Decision

When new dependencies' latest stable versions violate Rule 32 at the
moment of pin decision, AND no transitive conflict naturally
constrains uv to a Rule 32-compliant version, TenantShield adopts
tight upper bounds in ``pyproject.toml`` that explicitly exclude the
recent stables.

Concretely:

1. Identify the latest Rule 32-compliant version (released greater
   than or equal to 14 days).
2. Pin upper bound to the FIRST violating version (exclusive).
3. Document the deviation from semantic upper bounds via inline
   comment referencing this ADR.
4. Pin is temporary; revisit when violating versions age past 14 days.

Example applied in Block C (Tarea 2C.C.1):

    django = [
        "django>=4.2,<6.0.5",  # excludes 6.0.5 (released 10d ago, Rule 32). See ADR-0005.
    ]
    dev = [
        "django-stubs[compatible-mypy]>=6.0.3,<6.0.4",  # tight; see ADR-0005.
    ]

This locks lockfile to Django 6.0.4 + django-stubs 6.0.3, both Rule 32
compliant.

When upstream versions age past 14 days (typically 4-8 days forward
from decision date), upper bounds can be widened to semantic
boundaries (``<7.0``). This is a maintenance task, suitable for a
post-Sub-phase cleanup or dependabot automation in future phases.

## Alternatives considered

### Alternative A -- Loose semantic pin (``<7.0``)

Adopt clean semantic upper bound. Violates Rule 32 at decision time
(uv resolves to latest, which is less than 14 days).

**Rejected because:** explicit Rule 32 violation erodes discipline.
Project policy from Phase 0 establishes Rule 32; deviating per-case
without documented strategy weakens project process.

### Alternative B -- Defer Block C 4-8 days

Wait until violating versions age past 14 days, then pin cleanly with
``<7.0``.

**Rejected because:** Sub-phase 2C has invested significant
architectural work; stalling 4-8 days for timing accident of upstream
release cycle is disproportionate. Pin widening is a maintenance
task, not architectural; Block C's architectural deliverable
(ADR-0002 materialization, Django 6.0 matrix support) doesn't depend
on specific pin upper bounds.

### Alternative C -- Tight pin without ADR documentation

Same pins, no architectural documentation.

**Rejected because:** the strategy is recurring (3+ instances in Sub-
phase 2C). Documenting the meta-pattern in ADR-0005 provides audit
trail value, prevents re-derivation, and establishes precedent for
Phase 3+ (SQLAlchemy stubs ecosystem likely to surface similar
patterns).

## Consequences

### Positive

- Rule 32 discipline preserved.
- Block C proceeds today without delay.
- Reproducibility: lockfile locks to specific tested versions.
- Pattern documented for future recurrences.

### Negative

- Tight upper bounds require manual maintenance bumps as versions age.
- Anti-clean: upper bounds semantically arbitrary (``<6.0.5``
  excluding only one patch version vs ``<7.0`` excluding entire
  major).
- Possible CI matrix gaps if testing target versions older than locked
  versions.

### Maintenance workflow

When tight-pinned versions age past 14 days:

1. Verify newer versions cumple Rule 32 via PyPI check.
2. Widen upper bound to semantic boundary (typically
   ``<{major+1}.0``).
3. Run canonical battery + matrix cycle to confirm compatibility.
4. Commit as ``chore: widen <pkg> pin to <range> per ADR-0005
   maintenance``.

Recommended automation: dependabot configured to PR these bumps with
the maintenance workflow above.

## Empirical evidence

PyPI version ages verified at decision time:

- Django 6.0.4: 2026-04-07 (38 days, cumple Rule 32).
- Django 6.0.5: 2026-05-05 (10 days, VIOLATES Rule 32).
- django-stubs 6.0.3: 2026-04-18 (27 days, cumple Rule 32).
- django-stubs 6.0.4: 2026-05-09 (6 days, VIOLATES Rule 32).

uv lockfile post-pin resolves to Django 6.0.4 + django-stubs 6.0.3.
Matrix cycle on Django 4.2.30, 5.2.14, 6.0.4 all pass pytest (266
tests) + mypy (28 source files, 0 issues).

## References

- Rule 32 (sec 6 num 32: greater than or equal to 2 weeks for new
  dependencies, since Phase 0).
- ADR-0003 (Django 4.2 empirical CI testing).
- ADR-0004 (drf-stubs empirical CI testing).
- DR-014 (Django matrix support).
- PHASE_2C_KICKOFF.md sec 3 Block C (Django 6.0 matrix expansion).
