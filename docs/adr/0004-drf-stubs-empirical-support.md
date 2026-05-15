# ADR-0004 -- djangorestframework-stubs support via empirical CI testing

**Status:** Accepted.
**Date:** 2026-05-15.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.
**Related:** ADR-0003 (parallel pattern for Django 4.2 LTS).

## Context

Sub-fase 2C adopts Django REST Framework (DRF) as optional adapter
(`[drf]` extra introduced in Tarea 2C.0 with pin
`djangorestframework>=3.17.1,<4.0`). Following the typed-Django ecosystem
discipline established in Sub-fase 2A.1 (django-stubs as dev dep), the
natural addition is `djangorestframework-stubs[compatible-mypy]` to the
`[dev]` extra.

Empirical investigation during Tarea 2C.A.1 implementation revealed:

1. DRF itself does not ship `py.typed` marker. Without stubs, mypy
   strict mode produces 12 errors across 3 categories on the DRF
   adapter (`from rest_framework...` imports become `Any`, subclassing
   `BasePermission`/`PermissionDenied` violates `disallow_any_unimported`).

2. `djangorestframework-stubs` latest stable at 2026-05-15 is `3.17.0`
   (released 2026-05-13, age 2 days). Does NOT cumple Rule 32 / §6 #32
   filter (>2 weeks).

3. `djangorestframework-stubs 3.16.9` (released 2026-03-31, age 45 days)
   does cumple Rule 32. requires_dist: `django-stubs>=5.2.9` (compatible
   with current pin `django-stubs[compatible-mypy]>=5.2.9,<6.0`),
   `mypy<1.21,>=1.13` (compatible with mypy 1.19.1 installed).

4. The typeddjango ecosystem couples drf-stubs major version to
   django-stubs era: drf-stubs `3.16.x` works with django-stubs `5.x`,
   drf-stubs `3.17.x` requires django-stubs `>=6.0.4`. The version
   coverage of which DRF release each stubs version supports is NOT
   declared in PyPI classifiers; only `Framework :: Django` is
   declared.

This creates an analogous "by accident" pattern to the one ADR-0003
formalized for `django-stubs` covering Django 4.2: TenantShield's pin
of DRF 3.17.1 will be type-checked using drf-stubs 3.16.9, which
upstream does not explicitly declare covers DRF 3.17.x.

## Decision

TenantShield adopts `djangorestframework-stubs[compatible-mypy]>=3.16.9,<4.0`
in `[dev]` and commits to supporting DRF 3.17.x via empirical CI
testing, not via drf-stubs upstream declaration.

Concretely:

1. Pin: `djangorestframework-stubs[compatible-mypy]>=3.16.9,<4.0`.
2. The `[compatible-mypy]` extra activates DRF-stubs's mypy plugin
   alongside django-stubs's plugin, providing complete typed coverage
   for the DRF adapter under mypy strict mode.
3. DRF 3.17.x type checking succeeds against drf-stubs 3.16.9 in
   practice (empirically verified during Tarea 2C.A.0 ratification);
   undeclared by upstream classifiers.
4. The CI matrix runs mypy + pytest on the DRF adapter as the safety
   net. If a future drf-stubs release breaks DRF 3.17.x retro-
   compatibility, this CI cell will turn red and the ADR will be
   revisited.

## Alternatives considered

### Alternative A -- type: ignore dispersos in DRF adapter code

Add `# type: ignore[import-untyped, misc, no-any-unimported]` comments
across `permissions.py`, `mixins.py`, `serializers.py` (~10 ignores
distributed). Empirically counted during BLOCKER investigation.

**Rejected because:**

- Violates spirit of roadmap rule on `# type: ignore` discipline
  (each ignore requires specific code + justifying comment; 10
  dispersed ignores in 3 small files is silent typing debt).
- Suppresses real type-checking value of the typed-Django ecosystem.

### Alternative B -- [[tool.mypy.overrides]] module-level relaxation

Configure `disallow_any_unimported = false` + `ignore_missing_imports = true`
for `tenantshield.adapters.drf.*`.

**Rejected because:**

- Relaxes strict mode for the entire DRF adapter package.
- Future typing bugs in DRF code (3 modules + tests) would be
  silently ignored.
- Inconsistent with Sub-fase 2A.1 decision to keep django-stubs in dev:
  same disease (lack of typing) deserves same medicine (add stubs).

### Alternative C -- Pin latest drf-stubs 3.17.0 (violates Rule 32)

**Rejected because:**

- Latest stable has 2 days at the date of decision, violating sec 6
  num 32 / Rule 32 (greater than or equal to 2 weeks for new
  dependencies).
- Rule 32 is project policy from Phase 0; exceptions erode discipline.
- Additionally, drf-stubs 3.17.0 requires django-stubs>=6.0.4, which
  conflicts with current pin `<6.0`. Adopting 3.17.0 would force
  premature django-stubs bump, mixing scope with Block C.

### Chosen: drf-stubs 3.16.9 + ADR-0004 documentation

Pragmatic pin (3.16.9, cumple Rule 32) + explicit documentation of
the empirical-CI strategy (this ADR). Parallel pattern to ADR-0003.

## Consequences

### Positive

- Strict mode preserved across the entire codebase.
- DRF adapter has typed coverage during development (mypy + IDE
  autocomplete + refactoring safety).
- Zero `# type: ignore` in DRF adapter productive code.
- Pattern parallel to ADR-0003 (Django 4.2 empirical-CI): consistent
  precedent.
- Coupling drf-stubs 3.16.9 + django-stubs 5.x preserved; no Block C
  scope mixing.

### Negative

- A future drf-stubs release may break DRF 3.17.x retro-compatibility
  silently (not declared upstream).
- CI matrix is the safety net; if mypy starts failing on DRF adapter,
  this ADR must be revisited (bump drf-stubs to latest vs pin older).
- `mypy<1.21` ceiling in drf-stubs 3.16.9 [compatible-mypy] extra
  introduces silent debt: if mypy reaches 1.21 in the future,
  conflict implicit. Resolution natural at Block C (2C.C.1) when
  django-stubs is bumped: simultaneously bump drf-stubs to latest
  3.17.x or 3.18.x.

## Empirical evidence

The drf-stubs version comparison and conflict analysis was performed
empirically during the BLOCKER chain of Tarea 2C.A.1 (three BLOCKERs:
mypy strict on bare imports, Rule 32 violation of latest stable,
django-stubs coupling). Verified via PyPI JSON API:

- `djangorestframework-stubs 3.16.9` requires `django-stubs>=5.2.9`,
  `mypy<1.21,>=1.13`.
- `djangorestframework-stubs 3.17.0` requires `django-stubs>=6.0.4`,
  `mypy<2.2,>=1.13`.

The empirical record is preserved as inline content of Tarea 2C.A.0
report (commit message of `docs: register ADR-0004 + adopt drf-stubs pin`).

## References

- ADR-0003 (Django 4.2 empirical support) -- direct precedent.
- DR-019 (DRF integration scope: triple defense) -- this ADR enables
  the type-safe implementation of the triple defense.
- Roadmap v1.6 sec 6 Rule 32 (greater than or equal to 2 weeks for new
  dependencies).
- Roadmap v1.6 sec 6 Rule 40 (smoke scripts as specs subject to
  empirical validation).
- PHASE_2C_KICKOFF.md (kickoff document does not require retrospective
  adjustment; Block A/B/C/D order preserved).
