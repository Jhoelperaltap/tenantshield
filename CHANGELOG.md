# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0-alpha.0] - 2026-05-14

### Added
- Initial repository scaffolding and toolchain configuration (Phase 0).
- Package skeleton with PEP 561 typing marker.
- Smoke test suite with coverage gate at 95%.
- Pre-commit hooks: file hygiene, ruff, mypy, bandit, codespell.
- Django ORM enforcement adapter under `tenantshield.adapters.django`:
  - `@tenant_aware` decorator for opt-in model registration with custom
    `tenant_field` support.
  - `TenantAwareManager` injecting tenant filter via `get_queryset()`.
  - `TenantAwareQuerySet` propagating filter through chain operations
    with double-injection protection.
  - `_unscoped` escape hatch (plain Django Manager) for legitimate read
    bypass (note: signals still validate writes; see ADR-0002 and
    `docs/concepts/known-leaks.md` for full contract).
  - `pre_save` / `pre_delete` signal handlers with auto-fill on create
    (truthiness-based) and cross-tenant write rejection.
  - `TenantShieldConfig` Django AppConfig with `INSTALLED_APPS`
    integration.
  - System check `tenantshield.E001` verifying decorated models declare
    their referenced tenant field.
- Integration test infrastructure: `tests/integration/django/` with
  pytest-django + SQLite in-memory + testapp.
- CI matrix: Python 3.11, 3.12, 3.13 x Django 4.2, 5.2.

### Fixed

- `decorators.py`: replace Django auto-created plain `Manager` before
  installing `TenantAwareManager`, preventing silent enforcement bypass
  (commit `578652c`). Pattern from `django-polymorphic` and
  `django-modelcluster`.
- `managers.py`: inject tenant filter at `Manager.get_queryset()` entry
  point instead of overriding individual `QuerySet` read/write methods
  (commit `97db7f2`). Previous architecture caused infinite recursion
  in terminal methods (`count`, `get`, `exists`, `update`, `delete`)
  and bypassed filtering on `Model.objects.all()` since Django's Manager
  does not delegate to `QuerySet.all()`. Pattern from
  `django-tenant-schemas` and `django-tenants`.
- `signals.py`: auto-fill on create uses truthiness check (`not
  instance_tenant`) instead of identity (`is None`), capturing Django's
  CharField default of empty string in addition to None (commit
  `52f15ee`).

### Decision Records

The following decisions were made during Phase 0 execution and supersede or
clarify statements in `PHASE_0_KICKOFF.md`:

- **DR-001** — `pyproject.toml` `readme` and `[tool.hatch.version]` `path` require
  the referenced files to exist at any uv operation that resolves project metadata,
  including `uv lock`. `src/tenantshield/_version.py` and `README.md` were reclassified
  as build-time plumbing and created during Task 0.2 as minimal stubs, with their
  full content delivered in Tasks 0.3 and 0.6 respectively.
- **DR-002** — `__version__` in `_version.py` is declared without a type annotation
  (`__version__ = "0.0.1a0"`, not `__version__: str = "0.0.1a0"`). Hatchling's default
  regex source does not tolerate annotations, and the type is trivially inferable by
  mypy and pyright. The annotation added no value.
- **DR-003** — Commit signing (SSH/GPG) is deferred until before v0.5.0-alpha. The
  owner will configure local signing keys at that point. No retroactive signing of
  prior commits. ADR-0001 will document this decision formally when `docs/adr/` is
  established in Phase 1.
- **DR-004** — All commits, pull requests, issues, and project artifacts are
  attributed exclusively to human contributors. AI tooling is permitted but not
  credited in any project artifact. See `CONTRIBUTING.md` §Attribution.
- **DR-005** — Linter false positives on non-code content (legacy documentation in
  other languages, test fixtures, examples) are resolved by excluding the specific
  files in the tool's configuration, never by silencing the rule globally. First
  applied to `codespell` against `TENANTSHIELD_ROADMAP.md` in Task 0.5.
- **DR-006** — Dependabot uses the `uv` ecosystem identifier, not `pip`. GitHub
  Dependabot natively supports `uv` via the `dependabot-uv` adapter as of the
  date Phase 0 was executed. The `uv` ecosystem reads `uv.lock` directly,
  providing exact-version updates rather than range-based updates that `pip`
  would produce against `pyproject.toml`. Verified against
  `dependabot/dependabot-core` repository.
- **DR-007** — Test stack bumped to pytest `>=9.0.3,<10.0` and pytest-asyncio
  `>=1.3.0,<2.0` (where 1.3.0 is the latest stable verified at bump time).
  Driver: CVE-2025-71176 in pytest 8.x with no 8.x backport available. The
  pytest-asyncio bump is a forced consequence — pytest-asyncio `0.x` pinned
  itself to `pytest<9` and the `1.x` line is required for compatibility.
  Phase 0 smoke suite has no async tests; future Phase 1 async tests will be
  authored directly against pytest-asyncio 1.x semantics. The pytest-asyncio
  1.x changelog was reviewed for `asyncio_mode = "strict"` regressions before
  bumping.
- **DR-008** — Phase 1 is decomposed into three sub-phases (1A, 1B, 1C). Sub-phase
  1A delivers `tenantshield.exceptions` and `tenantshield.context` (tagged
  `v0.0.2-alpha.0`). Sub-phase 1B delivers `tenantshield.policies` and
  `tenantshield.audit` (tagged `v0.0.3-alpha.0`). Sub-phase 1C delivers
  `tenantshield.registry` plus mkdocs infrastructure and closes Phase 1
  entirely (tagged `v0.1.0-alpha`). The decomposition delivers verifiable value
  per sub-phase, forces intermediate documentation, and provides natural pause
  points for the owner.
- **DR-009** — `TenantId` is defined as `typing.NewType("TenantId", str)`. The
  internal bus is always `str` to eliminate serialization ambiguity across
  ORMs, transport layers, and persistence. User code is responsible for
  coercion at the system boundary (e.g. `TenantId(str(user.tenant_id))`).
  Public function signatures use `TenantId`, not bare `str`, to communicate
  semantic intent to readers and type checkers. Rejected alternatives:
  plain `str` (loses signal in code review), `TypeVar` (propagates genericity
  across 50+ signatures), Pydantic/dataclass (runtime overhead unnecessary
  for an identifier).
- **DR-010** — `structlog` is a base dependency, not an optional extra. Sub-phase
  1B introduces `StructLogSink` as a built-in `AuditSink`; making it conditional
  on an extra (`tenantshield[audit]`) added friction without proportional benefit
  given that `structlog` is a small, well-maintained package widely adopted in
  the Python ecosystem. The `tenantshield[*]` extras are reserved for heavier
  integrations (Django, SQLAlchemy, Celery, DRF, and future observability
  adapters like OpenTelemetry). Rejected alternatives: structlog in `[audit]`
  extra (friction, no clear benefit), structlog in `[dev]` only and forcing
  users to implement their own sink (hostile to adoption).
- **DR-011** — `RequireScope.filter_spec` is typed as `Mapping[str, object]`
  rather than a structured type (TypedDict, dataclass) in Sub-phase 1B.
  Rationale: at this stage there are no adapter consumers to dictate
  structure; imposing a schema now would either be too restrictive
  (forcing a shape that doesn't fit Django's ORM filter dicts, SQLAlchemy's
  clauses, Celery's task arguments) or too speculative. Adapters in Phase
  2+ may define their own structured `FilterSpec` subtypes that remain
  assignment-compatible with `Mapping[str, object]`. Rejected alternatives:
  TypedDict in `policies.py` (premature; binds the structure to Sub-phase
  1B's imagination), dataclass with concrete fields (even more rigid),
  `Any` (loses any typing benefit).
- **DR-012** — `ModelRegistry` exposed as a class with a global
  `default_registry` instance, plus module-level convenience functions
  (`register_model`, `is_tenant_aware`, `get_tenant_field`) that delegate
  to it. Users who need isolation construct their own `ModelRegistry()`
  and use it explicitly. Phase 2+ adapters will accept
  `registry: ModelRegistry | None = None` and fall back to
  `default_registry` when None. Rejected alternatives: module-level dict
  singleton (locks the project into shared global state, requires a
  breaking-change refactor if isolation becomes needed); ContextVar of
  registry (over-engineering — registries are static metadata, not
  runtime context; inconsistent with how Django/SQLAlchemy treat
  registries; problematic at import-time when most registration happens).
- **DR-013** — Django ORM enforcement uses custom `TenantAwareManager` +
  `TenantAwareQuerySet` as the primary interception mechanism (Sub-phase
  2A). Write-path validation supplements via `pre_save`/`pre_delete`
  signals (Sub-phase 2A). Low-level query interception (SQL inspection,
  monkey-patching of `_fetch_all`/`Compiler.execute_sql`) is **deferred
  to Phase 5** as a Query Analyzer paranoid mode — defense in depth via
  auditing, not primary enforcement. Rejected alternatives: pure
  signal-based interception (Django emits no signals during query
  compilation; would require monkey-patching private Django internals,
  fragile against version upgrades, violates §1.1.3 "no hidden magic");
  single-layer manager-only (leaves `_base_manager` and raw queries
  unprotected, but acceptable in pre-1.0 with documented user discipline
  and Phase 5 closing the gap).
- **DR-014** — Django adapter exposes `@tenant_aware` decorator (not a
  marker class via inheritance, not reuse of core `register_model`). The
  decorator: (1) registers the model in the core's `default_registry`
  via `register_model`, (2) replaces the model's default manager with
  `TenantAwareManager` (raising `ConfigurationError` if a custom manager
  already exists, with explicit `manager_class=` parameter for
  composition), (3) installs an `_unscoped` manager as documented escape
  hatch, (4) connects `pre_save`/`pre_delete` signals for write-path
  validation. Rejected alternatives: extending core `register_model` to
  do Django-specific work (violates core/adapter separation; same name
  with different behavior depending on import path is confusing); marker
  class via inheritance `TenantAware` (inconsistent with Sub-phase 1C's
  rejection of inheritance-based markers in the core; Django `Meta` MRO
  is delicate; obliges users with existing custom managers to refactor).
- **DR-015** — Sub-phase 2A integration tests use `pytest-django` +
  SQLite in-memory as the testing strategy. The enforcement logic of
  `TenantAwareManager`/`TenantAwareQuerySet` (`WHERE tenant_id = ?`
  injection) is database-agnostic; SQLite covers 100% of the testable
  logic in 2A. Rejected alternatives: testcontainers-postgres only
  (requires Docker locally and in CI; slows dev loop; raises adoption
  barrier for contributors; provides no additional coverage for 2A's
  actual logic); hybrid SQLite+Postgres via env var (over-engineering
  for 2A; pattern reserved for Phase 3 (SQLAlchemy) or when DB-specific
  features enter the codebase). Phase 3 or later sub-phases may
  introduce `TENANTSHIELD_TEST_POSTGRES=1` env var following the
  precedent of `TENANTSHIELD_BENCH_STRICT` (Sub-phase 1C).

### Architectural Decision Records

- **ADR-0001** — Commit signing deferred until immediately before the
  `v0.5.0-alpha` release tag. See `docs/adr/0001-commit-signing-deferral.md`.
- **ADR-0002** — Django 6.0 support deferred to Sub-phase 2C. See
  `docs/adr/0002-django-6-deferral.md`. Sub-phase 2A pins
  `django>=4.2,<6.0` covering LTS 4.2 and 5.2.
