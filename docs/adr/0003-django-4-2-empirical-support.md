# ADR-0003 -- Django 4.2 support via empirical CI testing

**Status:** Accepted.
**Date:** 2026-05-15.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.

## Context

During Sub-fase 2A.1, `django-stubs[compatible-mypy]>=5.2.9,<6.0` was
pinned in `pyproject.toml` to support the Django 4.2 LTS + 5.2 CI matrix
established by DR-014. The pin worked functionally: all 168 tests
(closed at `v0.2.0-alpha.0`) passed under both Django versions with mypy
strict + pyright clean.

However, an investigation during Sub-fase 2C pre-kickoff revealed a
silent assumption: **django-stubs upstream does not declare official
support for Django 4.2 in any current version.** The classifiers and
the version compatibility table of `django-stubs 5.2.9` reference only
Django 5.0, 5.1, 5.2; `django-stubs 6.0.3` adds Django 6.0 to its
declared support but maintains the same 5.0+ floor.

This means Django 4.2 LTS support in TenantShield has been "by accident"
since Sub-fase 2A.1 -- functionally green in CI, but undeclared by the
typing stubs upstream.

Sub-fase 2C requires pinning django-stubs to `6.0.x` to align with the
Django 6.0 matrix expansion (ADR-0002 materialization). The empirical
smoke pre-kickoff (Components 1-4 documented at
`docs/evidence/smoke_2c_premises.md`) verified that
`django-stubs 6.0.3` produces zero mypy errors and 228 passing tests
against Django 4.2.30. The "by accident" continues to work, but is
formally undeclared.

## Decision

TenantShield commits to supporting Django 4.2 LTS via **empirical CI
testing**, not via django-stubs declaration.

Concretely:

1. The pin `django-stubs[compatible-mypy]>=6.0,<7.0` is adopted in
   `pyproject.toml` for its officially declared coverage (Django 5.2
   full + 6.0 full).
2. Django 4.2 support is documented in this ADR as a conscious,
   accepted decision rather than a silent assumption.
3. The CI matrix includes the Django 4.2.30 cell with both pytest and
   mypy steps; if a future django-stubs release breaks Django 4.2
   retro-compatibility, this cell will turn red and the ADR will be
   revisited.

## Alternatives considered

### Alternative A -- Dual conditional stubs

Configure two separate django-stubs pins via conditional extras:

- `django-stubs[compatible-mypy]>=5.2.9,<6.0` for CI cells with Django 4.2/5.2.
- `django-stubs>=6.0,<7.0` for CI cells with Django 6.0.

**Rejected because:**

- Breaks `uv sync --all-extras --dev` coherence (cannot install both
  extras simultaneously).
- Developer experience locally suffers (which stubs version is active?).
- `pyproject.toml` complexity proliferates.

### Alternative B -- Loose range only (status quo + new pin)

Adopted as the pin strategy itself. Combined with this ADR (Alternative D
documentation) to formalize the decision.

### Alternative C -- Drop Django 4.2 from matrix

Subir el floor a `django>=5.2,<7.0`. Reduce matrix to 5.2 + 6.0.

**Rejected because:**

- Breaks the contract established in DR-014 and ADR-0002.
- Premature pre-1.0; users on Django 4.2 LTS (long-term support
  release) should benefit from TenantShield.

### Alternative D alone -- Status quo unchanged

Continue with `django-stubs>=5.2.9,<6.0` (Sub-fase 2A.1 pin),
ignoring the silent deuda.

**Rejected because:**

- Misses the Django 6.0 typing improvements.
- ADR-0002 materialization in Sub-fase 2C requires aligning stubs to 6.0.

### Chosen: B + D combined

Pragmatic pin (B) covering the matrix range + explicit documentation
of the empirical-CI strategy (D = this ADR).

## Consequences

### Positive

- Single stubs pin simplifies `pyproject.toml`.
- Matrix coverage remains broad (3 Django versions x 3 Python = 9 cells
  ready when CI activates).
- Django 4.2 LTS users continue to benefit from TenantShield without
  forced upgrade.
- The "by accident" pattern is formalized as conscious decision.

### Negative

- A future django-stubs release could break Django 4.2 retro-compatibility
  silently (not detected by upstream declaration).
- CI matrix is the safety net; if 4.2 cell starts failing on type-checking,
  this ADR must be revisited (drop 4.2 vs pin older stubs).
- Type-checking on Django 4.2 internals may have false positives or
  false negatives if django-stubs 6.x changes assumptions that differ
  from 4.2 behavior.

## Empirical evidence

`docs/evidence/smoke_2c_premises.md` archives the four components of
the pre-kickoff smoke that ratified the B+D strategy:

- Component 1: Django 6.0.4 + django-stubs 5.2.9 (228 tests pass).
- Component 2: Django 6.0.4 + django-stubs 6.0.3 (mypy 0 issues).
- Component 3: Django 4.2.30 + django-stubs 6.0.3 (CRITICAL: mypy 0 + 228 tests).
- Component 4: pytest-django 4.12.0 with Django 6.0.4 (transparent).

## References

- ADR-0002 (Django 6.0 deferral) -- this ADR materializes the deferred decision.
- DR-014 (Django 4.2 LTS support in matrix).
- Roadmap v1.6 section 6 Rule 40 (smoke scripts as specs).
- Roadmap v1.6 section 6 Rule 41 (PEP 621 not PEP 735 dependency management).
- `PHASE_2C_KICKOFF.md` section 2 (ADR-0003 inline definition).
