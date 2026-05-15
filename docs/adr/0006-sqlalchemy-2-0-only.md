# ADR-0006 -- SQLAlchemy 2.0+ only; drops 1.4 support

**Status:** Accepted.
**Date:** 2026-05-15.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.
**Related:** ADR-0002 (Django 6.0 deferral, same architectural
philosophy -- bump major when ecosystem stable), Rule 32 (sec 6 num 32:
greater than or equal to 14 days for new dependencies).

## Context

Phase 3 of TenantShield introduces a SQLAlchemy adapter. The Python
SQLAlchemy ecosystem currently exists in two major versions:

- **SQLAlchemy 1.4** (released March 2021): legacy `Query` API,
  optional external `sqlalchemy-stubs` for typing, declarative via
  `declarative_base()` function. Status: maintenance-only since
  SA 2.0 release.
- **SQLAlchemy 2.0** (released January 2023): unified Core + ORM API,
  PEP 561 inline typing via `py.typed` marker, declarative via
  `DeclarativeBase` class + `Mapped[T]` typing, `select()` statements
  replacing `Query`. Status: actively developed, current minor 2.0.49
  released 2026-04-03.

The 1.4 to 2.0 API divergence is substantial:

- Read queries: `session.query(Foo)` (1.4) vs
  `session.execute(select(Foo))` (2.0).
- Type annotations: external stubs (1.4) vs inline `Mapped[T]` (2.0).
- Declarative base: function (`declarative_base()`) vs class
  (`DeclarativeBase`).
- Event listener registration: similar but session-scoping behavior
  differs.

Supporting both versions would require dual code paths in the adapter
for query interception, mapper introspection, and event listener
registration. Test surface would approximately double.

## Decision

TenantShield's SQLAlchemy adapter (Phase 3 onwards) supports **only
SQLAlchemy 2.0+**. The `sqlalchemy` optional extra in `pyproject.toml`
declares `sqlalchemy>=2.0,<3.0`. Adopters running SQLAlchemy 1.4 must
either upgrade to 2.0 or remain on TenantShield's Django adapter
(Phase 2) until migrating.

Rationale:

1. **Maintenance status:** SA 1.4 is in maintenance-only mode since
   January 2023. New features, ecosystem improvements, and ongoing
   support concentrate on 2.0.
2. **Typing maturity:** SA 2.0 ships PEP 561 inline typing via
   `py.typed` marker. Empirical verification (pre-Phase-3 smoke,
   2026-05-15) confirmed:

   - `py.typed` marker exists in installed package.
   - `mypy --strict` succeeds on canonical SA 2.0 patterns.
   - `reveal_type()` correctly infers `Mapped[T]` columns.
   - No `sqlalchemy-stubs` required as parallel dev dependency.

3. **Cost of dual support:** approximately 2x test surface, dual
   adapter code paths for query interception (`Query` vs `select()`),
   ongoing maintenance overhead during SA 2.0 patch cycle.
4. **Ecosystem velocity:** modern Python projects targeting 2026+
   adopt SA 2.0. Supporting 1.4 would slow Phase 3 delivery without
   meaningful adopter base.
5. **Future-proof:** SA 2.0+ unified API is the documented forward
   direction; SA 3.0 (whenever released) is expected to be evolution
   of 2.0, not 1.4 fork.

## Alternatives considered

### Alternative A -- Support both SA 1.4 and SA 2.0

Implement parallel code paths for `Query`-style (1.4) and
`select()`-style (2.0) queries. Dual test matrix.

**Rejected because:** doubles test surface for marginal adopter base
gain. SA 1.4 maintenance-only status means adopter migration to 2.0
is inevitable. Investing in 1.4 compatibility delays Phase 3 delivery
without sustainable benefit.

### Alternative B -- SA 1.4 only (legacy adopter focus)

Target adopters who haven't migrated to 2.0 yet.

**Rejected because:** maintenance-only ecosystem stance signals
inevitable deprecation. Building an adapter against legacy API would
require immediate redesign as adopters migrate to 2.0.

### Alternative C -- SA 2.0+ with explicit `sqlalchemy-stubs` parallel pin

Add `sqlalchemy-stubs[compatible-mypy]` to dev extras for typing
robustness.

**Rejected because:** empirical verification (pre-Phase-3 smoke)
confirmed `py.typed` inline typing sufficient. Adding stubs duplicates
typing infrastructure, may cause conflict with inline annotations,
and brings the ecosystem into typeddjango-velocity zone (Rule 47
applicability). Inline typing simplifies dependency chain.

## Consequences

### Positive

- Single API target simplifies adapter implementation.
- PEP 561 inline typing simplifies dev dependencies (no stubs needed).
- Modern declarative pattern (`DeclarativeBase` + `Mapped[T]`)
  ergonomic for adopters.
- Future-proof: SA 2.0+ is the active development branch.

### Negative

- Adopters running SA 1.4 cannot use TenantShield SQLAlchemy adapter
  until they migrate. Communication: README documents requirement
  explicitly; pyproject extra pin `>=2.0,<3.0` makes constraint clear.
- Phase 4+ may need additional ADR if SA 3.0 emerges and breaking
  changes warrant. Current pin upper bound `<3.0` provides safety.

### Long-term

- When SA 3.0 emerges (no known timeline), revisit pin upper bound.
  Pattern: smoke verify compatibility, evaluate breaking changes,
  bump pin or fork code path.
- If sqlalchemy-stubs ecosystem develops for any reason (e.g., third-
  party plugin types), ADR-0007+ may revisit dual typing posture.

## Empirical evidence

Pre-Phase-3 smoke verification (2026-05-15):

- SQLAlchemy 2.0.49 latest stable, 42 days old (Rule 32 PASS).
- Empirical SA 2.0.x release cadence: monthly (2.0.45 to 2.0.46 to
  ... to 2.0.49 over 5 months). Stable predictable cycle.
- `py.typed` marker exists in installed package at
  `<venv>/lib/site-packages/sqlalchemy/py.typed`.
- PyPI classifier `Typing :: Typed` absent (datapoint: classifier vs
  marker divergence; empirical inspection of marker file is the
  authoritative check).
- `mypy --strict` succeeds on canonical SA 2.0 declarative + Mapped
  pattern with `reveal_type()` correctly inferring `str` and `int`.

## References

- SQLAlchemy 2.0 release notes:
  <https://docs.sqlalchemy.org/en/20/changelog/migration_20.html>.
- SA 2.0 typing documentation:
  <https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html>.
- ADR-0002 (Django 6.0 deferral, analogous pattern of major version
  targeting).
- Rule 32 (sec 6 num 32: greater than or equal to 14 days for new
  dependencies, Phase 0).
- Pre-Phase-3 smoke verification report (2026-05-15, this date).
- Phase 3A kickoff document (`PHASE_3A_KICKOFF.md`, local-only).

---

**End of ADR-0006.**
