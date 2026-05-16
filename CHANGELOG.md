# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `tenantshield[sqlalchemy]` optional dependency extra declaring
  `sqlalchemy>=2.0,<3.0`. Foundation for Phase 3 SQLAlchemy adapter
  (in progress).

### Decision Records (pending tag)

- **DR-023** -- SQLAlchemy raw SQL via `text()` bypasses ALL tenant
  enforcement layers. Raw SQL statements skip `do_orm_execute` filter
  injection (handler guard:
  `if not (state.is_select and state.is_orm_statement): return`) and
  skip mapper-scoped events (`before_insert`, `before_update`,
  `before_delete`) because text statements do not trigger mapper
  machinery. This is an intentional architectural constraint matching
  Django adapter's `_base_manager` semantics. Raw SQL is the documented
  escape hatch for adopter operations requiring full control. Adopters
  using `session.execute(text("..."))` inherit complete responsibility
  for tenant coherence; library cannot enforce safety on opaque SQL
  text. Pattern analogous to DR-024 (bulk operations bypass mapper
  events). Together, DR-023 + DR-024 establish the bypass semantics
  surface for the SQLAlchemy adapter. Materialized in Sub-fase 3A
  Tarea 3A.7 with empirical evidence + 9 test cases documenting bypass
  behavior. See ADR-0007 consequences section.
- **DR-024** -- SQLAlchemy bulk operations bypass mapper-scoped events.
  `session.execute(insert(Foo).values([...]))`,
  `session.execute(update(Foo).where(...).values(...))`, and
  `session.execute(delete(Foo).where(...))` bypass the `before_insert`,
  `before_update`, and `before_delete` events respectively. This is
  SQLAlchemy's documented behavior for performance reasons.
  Consequence: tenant enforcement on write paths is NOT applied to
  bulk operations. Adopters using bulk patterns must manually validate
  tenant coherence in application code. Read operations via
  `session.execute(select(Foo))` are still filtered by
  `do_orm_execute` event regardless of bulk or individual fetch
  pattern. Pattern analogous to Django adapter's `_base_manager`
  semantics. Materialized in Sub-fase 3A Tarea 3A.6 with empirical
  evidence + 5 test cases documenting bypass behavior. See ADR-0007
  consequences section.
- **DR-025** -- SQLAlchemy adapter enforcement fires at flush time,
  not at `session.add()` / `session.delete()` time. Implications:
  tenant scope must be active at flush (whether explicit
  `session.flush()`, autoflush before a query, or implicit flush
  during `session.commit()`); scope changes between `add()` and
  `flush()` use the scope active AT FLUSH TIME (auto-injection
  reflects flush-time scope, not add-time scope); autoflush (default
  in SA 2.0) triggers events before SELECT queries, so tenant scope
  must be active for queries with pending writes; expunged instances
  (`session.expunge()`) do not fire events because the instance is
  no longer tracked by the session. Adopter guidance: keep tenant
  scope active throughout session operations, not only during
  instance construction. Pattern paralelo a Django adapter's signal
  firing at `model.save()` time; SA adapter's flush-time firing
  matches SA's session lifecycle. Together with DR-021 (write
  enforcement) and DR-022 (read enforcement), DR-025 establishes the
  complete timing semantics of the adapter. Materialized in Sub-fase
  3A Tarea 3A.9 with empirical evidence + 7 test cases across flush,
  autoflush, commit, and expunge timing points. See ADR-0007
  (event-based enforcement) for related architectural context.

### Architectural Decision Records (pending tag)

- **ADR-0006** -- SQLAlchemy 2.0+ only; drops 1.4 support. Single
  major-version target simplifies adapter implementation; PEP 561
  inline typing eliminates need for parallel stubs package.
  Materialized in Sub-fase 3A Tarea 3A.0.
- **ADR-0007** -- Event-based enforcement for SQLAlchemy adapter.
  Materializes Decision 4-A from PHASE_3A_KICKOFF.md. Three event
  mechanisms compose tenant enforcement:
  `before_insert`/`before_update`/`before_delete` mapper-scoped
  events for writes; `do_orm_execute` session-scoped event for
  reads via `with_loader_criteria` injection (static SQL expression,
  not lambda — SA caches loader-criteria lambdas by body and ignores
  closure variables). Reads fall through on missing scope; stricter
  raise-on-missing behavior provided by middleware in Sub-fase 3B.
  Materialized evidence-based in Sub-fase 3A Tarea 3A.5.

## [0.2.0-alpha] -- 2026-05-15

### Phase 2 summary

Phase 2 of TenantShield delivers complete Django adapter coverage
across the full request lifecycle. The release closes three sub-phases:

- **Sub-phase 2A (`v0.2.0-alpha.0`)** -- ORM-level enforcement via
  `@tenant_aware` decorator, `TenantAwareManager`,
  `TenantAwareQuerySet`, and write-time signal handlers (`pre_save`,
  `pre_delete`).
- **Sub-phase 2B (`v0.2.0-alpha.1`)** -- `TenantContextMiddleware`
  with composable extraction strategies (Header, Subdomain, JWT,
  Callable) + Protocol contract + strategy resolver.
- **Sub-phase 2C (this release)** -- DRF integration via three
  independent enforcement layers (DR-019 triple defense), runnable
  example mini-project, Django 6.0 matrix expansion, and ADR-0005
  documenting meta-pattern for typeddjango ecosystem version
  management.

### Acceptance gates (8/8 met)

- All 266 tests pass on Django 4.2.30 LTS / 5.2.14 / 6.0.4 (matrix
  cycled locally; CI definition ready for future remote activation).
- Coverage 99.88% global, greater than or equal to 95% per module
  (gate greater than or equal to 95%).
- mypy strict + pyright clean + ruff clean + 13/13 pre-commit hooks
  green.
- Public surface stable: 18 canonical imports verified working
  (Core 4 + Django adapter 4 + Strategies 6 + DRF adapter 4).
- Example mini-project boots and serves multi-tenant API per README
  walkthrough.
- 5 ADRs documenting architectural decisions (0001-0005).
- 8 Decision Records added across Phase 2 (DR-013 through DR-020).
- All sub-phase tags preserved (`v0.2.0-alpha.0`, `v0.2.0-alpha.1`).

### Added (Sub-phase 2C)

- DRF adapter at `tenantshield.adapters.drf`: 5 modules implementing
  the DR-019 triple defense.
  - `IsSameTenant` permission (request-level + object-level
    enforcement at the view boundary).
  - `TenantAwareViewSetMixin` (queryset-level enforcement when manager
    is absent or bypassed via `_base_manager`).
  - `TenantValidatedSerializerMixin` (write-path enforcement with
    `to_internal_value` auto-inject + `create`/`update` mismatch
    detection).
  - `TenantPermissionDenied` DRF-adapter exception (HTTP 403 by
    default via DRF default exception handler).
- Optional dependency extra `[drf]` with `djangorestframework>=3.17.1,<4.0`.
- `examples/01_django/` runnable mini-project demonstrating
  end-to-end multi-tenant isolation with Django + DRF + TenantShield.
  Includes `pyproject.toml`, `manage.py`, settings + URLs + WSGI/ASGI,
  `Org` and `Invoice` models decorated with `@tenant_aware`,
  serializers + viewsets + URL routes consuming the DRF adapter, and
  a comprehensive README (curl walkthrough, architecture notes,
  common gotchas).
- 24 unit + integration tests for the DRF adapter at
  `tests/integration/django/test_drf.py` (Permission + Mixin +
  Serializer classes, plus 6 end-to-end tests via DRF `APIClient`
  against the `testapp`).
- 8 structural smoke tests for the example mini-project at
  `tests/integration/examples/test_01_django.py`.
- CI matrix expanded to 9 cells (Python 3.11 / 3.12 / 3.13 x
  Django 4.2 / 5.2 / 6.0).

### Decision Records (Sub-phase 2C)

- **DR-019** -- DRF adapter triple-defense architecture. Three
  independent layers acting at distinct points of the DRF request
  lifecycle (Permission at request/object boundary, ViewSet Mixin at
  queryset construction, Serializer Mixin at write-path validation),
  NOT composable filters on a single queryset (architectural truth
  discovered empirically during the 8 BLOCKERs of Block A; docstrings
  document Pattern A vs Pattern B usage). Rejected alternatives:
  permission-only (misses queryset bypass + write-path validation),
  middleware-only (DRF Router paths can bypass Django middleware
  in some configurations).
- **DR-020** -- Examples directory architecture. `examples/01_django/`
  is a self-contained mini-project with its own `pyproject.toml`,
  editable install of TenantShield, and dedicated venv. README
  walkthrough is the canonical adopter reference. Numbered prefix
  reserves space for future adapters (`02_sqlalchemy/`,
  `03_celery/`).

### Architectural Decision Records (ADR-0003 through ADR-0005)

- **ADR-0003** -- Django 4.2 LTS support via empirical CI testing,
  not via django-stubs upstream declaration. See
  `docs/adr/0003-django-4-2-empirical-support.md`. The CI matrix
  includes the Django 4.2.30 cell with both pytest and mypy steps
  as the empirical safety net.
- **ADR-0004** -- djangorestframework-stubs support via empirical CI
  testing (parallel pattern to ADR-0003). Adopts pin
  `djangorestframework-stubs[compatible-mypy]>=3.16.9,<4.0` for
  type-safe DRF adapter coverage under mypy strict mode. DRF 3.17.x
  is type-checked using drf-stubs 3.16.9 in practice; upstream
  classifiers do not declare specific DRF version coverage. See
  `docs/adr/0004-drf-stubs-empirical-support.md`.
- **ADR-0005** -- Tight upper bounds strategy for typed-Django
  ecosystem pins violating Rule 32 (greater than or equal to 14 days
  for new dependencies). Sub-phase 2C Block C adopts
  `django>=4.2,<6.0.5` + `django-stubs[compatible-mypy]>=6.0.3,<6.0.4`
  because Django 6.0.5 (10 days at decision date) and django-stubs
  6.0.4 (6 days) violated Rule 32 at the moment of pin widening.
  Documents the recurring pattern (3+ instances in Sub-phase 2C
  alone) for future recurrences in Phase 3+. See
  `docs/adr/0005-tight-upper-bounds-strategy.md`.

### Architecture milestones reached

- Django adapter: complete (ORM in 2A + middleware in 2B + DRF
  triple defense in 2C).
- 3 supported Django versions (4.2 LTS + 5.2 + 6.0) verified across
  the local matrix cycle.
- 5 DRF adapter modules at 100% line + branch coverage.
- Runnable mini-project demonstration available for adopters.
- 5 architectural decision records (ADR-0001 through ADR-0005).
- 8 decision records added across the phase (DR-013 through DR-020).

### See also

- See the `[0.2.0-alpha.0]` section below for full Sub-phase 2A
  details (ORM + signals).
- See the `[0.2.0-alpha.1]` section below for full Sub-phase 2B
  details (middleware + extraction strategies).

## [0.2.0-alpha.1] -- 2026-05-15

Sub-phase 2B complete -- Django middleware + tenant extraction strategies.

### Added

- `TenantContextMiddleware` -- Django middleware composing one of four
  extraction strategies, binding tenant via `bind_tenant`, and wrapping
  `get_response` in `tenant_scope` for the request lifecycle.
- Four built-in extraction strategies implementing the
  `TenantExtractionStrategy` Protocol: `SubdomainStrategy` (extracts
  leftmost host label), `HeaderStrategy` (configurable HTTP header,
  default `X-Tenant-Id`), `JWTStrategy` (decodes Bearer token via PyJWT,
  configurable claim and algorithm), `CallableStrategy` (wraps a
  user-provided function).
- `resolve_strategy(config)` factory translating Django settings dict
  to a strategy instance.
- Three new system checks: `tenantshield.E002` (middleware in
  `MIDDLEWARE` but `tenant_extraction` not configured),
  `tenantshield.W001` (`on_missing_tenant="public"` visibility),
  `tenantshield.W002` (registered models exist but middleware absent).
- Optional dependency extra `[jwt]` with `pyjwt>=2.12.1,<3.0` for the
  `JWTStrategy`.
- `TenantExtractionError` adapter-specific exception raised by
  strategies when the tenant cannot be extracted, translated by the
  middleware to the configured `on_missing_tenant` behavior.

### Decision Records

- **DR-016** -- Tenant extraction strategies architecture for Django
  middleware. Pattern: Protocol-based dispatch via
  `TenantExtractionStrategy` Protocol with four built-in implementations.
  Resolution via `resolve_strategy(config)` function. Middleware
  composes one strategy at a time; multi-strategy chains deferred.
- **DR-017** -- `on_missing_tenant` configurable behavior in Django
  middleware. Default `"raise"` honors fail-closed posture (DR-005).
  Alternatives `"404"`, `"public"`, and callable cover real use cases:
  health checks, public APIs mixed with tenant APIs, custom error
  responses.
- **DR-018** -- System check severity strategy for Django middleware.
  `tenantshield.E002` (Error) when middleware installed but no strategy
  configured. `tenantshield.W001` (Warning) on `on_missing_tenant="public"`.
  `tenantshield.W002` (Warning) when `@tenant_aware` models exist but
  middleware not installed -- programmatic usage is legitimate.

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
