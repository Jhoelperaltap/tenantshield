# ADR-0002 -- Django 6.0 support deferred to Sub-phase 2C

* **Status:** Accepted
* **Date:** 2026-05-14
* **Deciders:** Tech Lead, Owner
* **Phase:** Sub-phase 2A consolidation
* **Supersedes:** None
* **Superseded by:** None (active)

## Context

Django 6.0 became stable on 2025-12-03, approximately 5.5 months before
Sub-phase 2A of TenantShield began. At the time of Sub-phase 2A's
opening kickoff, the actively-supported Django versions were:

- Django 4.2 LTS (released April 2023, extended support active).
- Django 5.2 LTS (released April 2025, mainstream support active).
- Django 6.0 (released December 2025, current mainline).

The TenantShield Phase 1 roadmap committed to supporting Django 4.2 LTS
as a baseline because many production deployments remain on LTS series
for stability. Supporting Django 6.0 in Sub-phase 2A simultaneously
with 4.2 LTS would require either:

1. Single django-stubs pin covering both Django 4.2 through 6.0 (not
   currently available; django-stubs series follows Django series:
   stubs 5.2.x for Django 4.2 / 5.2, stubs 6.0.x for Django 6.0).
2. Dual stubs pin with compatibility shims.
3. Forking type-checking into per-version configurations.

All three increase typing complexity and CI matrix size during initial
adapter development.

## Decision

Sub-phase 2A supports Django 4.2 LTS and 5.2 only.
`pyproject.toml` pins `django>=4.2,<6.0`. CI matrix is
`python: 3.11, 3.12, 3.13` x `django: 4.2, 5.2` (6 cells).

Django 6.0 support is deferred to Sub-phase 2C, which will:

1. Expand the CI matrix to include Django 6.0 (3 x 3 = 9 cells, or
   adjusted matrix per resource considerations at that time).
2. Introduce django-stubs 6.x pin alongside 5.2.x with the appropriate
   typing strategy (dual pin or unified compatibility approach decided
   at that point based on django-stubs ecosystem state).
3. Verify backward compatibility with Django 4.2 LTS and 5.2 is
   preserved.
4. Update `pyproject.toml` cap from `<6.0` to `<7.0`.

## Consequences

### Positive

- Sub-phase 2A delivers a complete, tested adapter for the two
  most-deployed Django versions without typing complexity from dual
  stubs.
- LTS users (the conservative production majority) get full support
  from the first release of the adapter.
- CI matrix during initial adapter development stays at 6 cells,
  containing CI cost.

### Negative

- Pre-2C users running Django 6.0 must wait for Sub-phase 2C closure
  (`v0.2.0-alpha` tag) to use TenantShield, or temporarily pin Django
  to `<6.0` in their environment.
- The cap `django>=4.2,<6.0` is visible in `pyproject.toml` and may
  prompt user questions; mitigated by README documentation and this
  ADR.

### Neutral

- Sub-phase 2B (middleware) is not affected by this decision; middleware
  contracts are stable across Django 4.2 to 6.0.

## Alternatives considered

### Alternative A -- Support 4.2 + 5.2 + 6.0 from Sub-phase 2A

Rejected because:

- Dual django-stubs pin increases typing complexity at a stage where
  the adapter is being designed; would distract from core architectural
  decisions (DR-013, DR-014, DR-015).
- Additional CI matrix cells (9 instead of 6) during the most expensive
  phase of adapter implementation.
- Scope creep for Sub-phase 2A's primary goal (ORM enforcement core).

### Alternative B -- Drop Django 4.2 LTS in favor of 5.2 + 6.0 only

Rejected because:

- Breaks the Phase 1 roadmap commitment to LTS support.
- Excludes the conservative production majority running 4.2 LTS.
- Django 4.2 LTS extended security support continues through 2026 and
  beyond; dropping it would be premature.

### Alternative C -- Conservative cap with no plan for Django 6.0

Rejected because:

- Indefinite pin to `<6.0` would create growing technical debt.
- Users seeing `<6.0` cap without an ADR explanation would correctly
  question the project's commitment to keeping current.
- This ADR records the deferral with a definite plan and timeline.

## Implementation notes

- `pyproject.toml` `[project.optional-dependencies].django` and
  `[project.optional-dependencies].dev` pin `django>=4.2,<6.0` until
  Sub-phase 2C closure.
- `.github/workflows/ci.yml` matrix declares `django-version:
  ["4.2", "5.2"]` until Sub-phase 2C closure.
- `django-stubs[compatible-mypy]>=5.2.9,<6.0` is the matching stubs pin.
- Sub-phase 2C kickoff will reference this ADR explicitly and document
  the version-expansion implementation.

## References

- DR-013, DR-014, DR-015 (Sub-phase 2A Decision Records).
- `PHASE_2A_CLOSURE.md` Section 11.
- Django release history (verified via PyPI JSON API on 2026-05-14).
