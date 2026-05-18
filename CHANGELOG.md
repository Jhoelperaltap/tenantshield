# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

(Pending entries for Block C Phase 4 closure: examples cross-validation,
pin audit per Rule 61, ``__version__`` bump to ``0.4.0a0`` per Rule 49,
and Phase 4 closure summary.)

## [0.4.0-alpha.1] -- 2026-05-17

### Sub-fase 4B summary

Sub-fase 4B delivers cross-adapter tenant extraction strategy
unification, closing the BLOCKER #30 deferral originated in Sub-fase
2B and re-confirmed for Path (c) ratification in Sub-fase 3B.

A new top-level ``tenantshield.strategies`` module hosts framework-
agnostic strategies (``HeaderStrategy``, ``HostStrategy``,
``JWTStrategy``, ``CallableStrategy``) operating on a minimal
``RequestProtocol`` abstraction. Adapter-specific request wrappers
(``DjangoRequestAdapter`` in the Django adapter, ``AsgiRequestAdapter``
in the SQLAlchemy adapter) bridge framework-specific request types to
the protocol. A cross-adapter ``resolve_strategy()`` factory function
is re-exported at three paths (core / SA adapter / top-level
``tenantshield``) with identical symbol identity.

Phase 2B Django adopters retain their import paths and Phase 2B
raise-on-missing contract via subclass shim layer; 117/117 existing
Django strategy tests pass unchanged.

### Acceptance gates (8/8 met)

- 474 library tests passing on canonical Python 3.13 + SA 2.0.49 +
  aiosqlite 0.22.1 (62 new tests added in Sub-fase 4B: 27 core
  strategies + 6 DjangoRequestAdapter + 12 AsgiRequestAdapter + 9
  resolve_strategy + 8 cross-adapter integration).
- 16 example tests passing (5 CLI + 5 Flask + 6 FastAPI async)
  isolated from main library suite.
- Library coverage 99.59% (gate >=95%); modest delta from Sub-fase
  4A's 99.91% reflects Protocol stub bodies (``...`` method placeholders
  in ``tenantshield.strategies.base``) and the PyJWT ImportError fallback
  in ``tenantshield.strategies.jwt``.
- mypy strict + pyright clean + ruff clean + 13/13 pre-commit hooks
  green.
- Public surface stable + extended: 37 canonical imports (Core 4 +
  Django adapter 4 + Strategies 6 + DRF adapter 4 + SQLAlchemy adapter
  9 + cross-adapter strategies 7 + adapter wrappers 2 +
  ``resolve_strategy`` 1).
- 10 ADRs documenting architectural decisions (0001-0010).
- 35 Decision Records (DR-001 through DR-027 SKIPPED + DR-028..036).
- Sub-fase tag ``v0.4.0-alpha.1`` applied at this release.
- BLOCKER #30 deferral empirically closed end-to-end via 8 integration
  tests demonstrating the same strategy class instance extracts
  identical tenant values via both ``DjangoRequestAdapter`` and
  ``AsgiRequestAdapter`` (Tarea 4B.5).

### Added

- ``tenantshield.strategies`` cross-adapter core module:
  - ``RequestProtocol`` -- minimal request interface
    (``get_header(name)`` + ``get_host()``); ``@runtime_checkable``
    for adopter test ergonomics.
  - ``TenantExtractionStrategy`` -- protocol for strategies operating
    on ``RequestProtocol``.
  - ``TenantExtractionError`` -- cross-adapter extraction failure
    exception (kwarg-only constructor; distinct from Django adapter's
    Phase 2B class).
  - ``HeaderStrategy``, ``HostStrategy``, ``JWTStrategy``,
    ``CallableStrategy`` -- four framework-agnostic strategies
    returning ``TenantId`` on success, ``None`` on fall-through, and
    raising ``TenantExtractionError`` on irrecoverable failure.
  - ``resolve_strategy(config)`` -- cross-adapter factory raising
    ``ValueError`` for misconfiguration (Python-idiomatic; distinct
    from Django adapter factory which raises
    ``ImproperlyConfigured`` per Phase 2B / DPRJ-2 preservation).
- ``tenantshield.adapters.django.middleware.strategies.DjangoRequestAdapter``
  -- wraps Django ``HttpRequest`` to conform to ``RequestProtocol``.
  Bridges WSGI ``META`` dict access + ``get_host()`` method to the
  protocol surface (Decision iii-A).
- ``tenantshield.adapters.sqlalchemy.AsgiRequestAdapter`` -- wraps
  ASGI scope dict to conform to ``RequestProtocol``. Bridges header
  list-of-byte-tuples to case-insensitive string lookup; derives host
  from the ``Host`` header (Decision iii-A).
- Top-level ``tenantshield`` re-exports cross-adapter strategies +
  ``resolve_strategy`` per Phase 1 core re-export pattern (top-level
  symbol identity matches adapter-level re-exports).

### Changed

- Django strategies (``HeaderStrategy``, ``JWTStrategy``,
  ``SubdomainStrategy``, ``CallableStrategy``) refactored in-place as
  subclasses of ``tenantshield.strategies`` core. Each subclass
  overrides ``extract`` to wrap ``HttpRequest`` in
  ``DjangoRequestAdapter`` and translate the core return-``None``
  contract back to Phase 2B raise-``TenantExtractionError`` for
  backward compatibility (Decision 6-A). Adopter imports + behavior
  preserved exactly; 117/117 existing Django strategy tests pass
  unchanged.
- ``SubdomainStrategy`` retained as a subclass alias of
  ``HostStrategy``; cross-adapter use prefers ``HostStrategy``
  (Decision 5-B).
- ``CallableStrategy`` (Django adapter): adopter callable continues
  to receive the raw ``HttpRequest`` (preserving Phase 2B contract
  where callables use ``request.GET``, ``request.session``, etc.).
  The cross-adapter core ``CallableStrategy``, in contrast, passes
  the ``RequestProtocol``-conforming object to the callable.

### Decision Records

- **DR-033** -- ``RequestProtocol`` minimal surface. Empirically
  determined in Tarea 4B.0 to require only two methods
  (``get_header(name)``, ``get_host()``) to cover all four built-in
  strategies. Cross-adapter feasibility validated by
  ``DjangoRequestAdapter`` + ``AsgiRequestAdapter`` both conforming
  via ``isinstance(adapter, RequestProtocol)`` at the
  ``@runtime_checkable`` Protocol level. Optional surface additions
  (query params, cookies, body) deferred until adopter demand.
- **DR-034** -- In-place Django strategy refactor preserves public
  API via subclass shim layer (Decision 6-A). Phase 2B adopter
  imports + raise-on-missing contract preserved; 117/117 Django
  strategy tests pass unchanged. Subclass approach surgical: each
  Django strategy subclasses the core strategy, overrides
  ``extract(request: HttpRequest) -> TenantId`` to wrap the request
  in ``DjangoRequestAdapter``, delegate to ``super().extract()``, and
  translate the core's two-tier contract (return ``None`` on missing)
  back to the Phase 2B single-tier contract (raise
  ``TenantExtractionError``).
- **DR-035** -- SA strategy class parity scope: Option (gamma)
  ratified empirically -- the SA adapter does not require subclass
  strategies because Phase 3B used callable-resolver only (no
  legacy Phase 3B strategy classes to preserve). The SA adapter
  re-exports the core strategies + provides ``AsgiRequestAdapter``.
  Symmetric to Django's adapter-level wrapper pattern (Decision
  iii-A) without subclass overhead.
- **DR-036** -- ``HostStrategy`` generic host parser replaces Django-
  specific ``SubdomainStrategy`` for cross-adapter use (Decision
  5-B). Parsing logic (port strip, leftmost-label extraction,
  three-label minimum for subdomain extraction) is HTTP-standard
  and not Django-specific; transferable as-is via ``RequestProtocol
  .get_host()``. Django adopters keep the ``SubdomainStrategy``
  symbol as a subclass alias of ``HostStrategy`` for Phase 2B
  backward compatibility (Decision 6-A).

### Architectural Decision Records

- **ADR-0010** -- Cross-adapter strategy unification. Documents the
  seven architectural pillars: ``RequestProtocol`` minimal surface
  (Decision 4-A + DR-033), adapter wrappers at adapter level
  (Decision iii-A), ``HostStrategy`` generic replacement (Decision
  5-B + DR-036), in-place Django refactor with re-export shim
  (Decision 6-A + DR-034), adopter-facing callable surfaces preserve
  framework-native types, cross-adapter ``resolve_strategy()``
  factory, and ``TenantExtractionError`` in
  ``tenantshield.strategies`` (Decision ii-B). Three alternatives
  rejected with rationale (async-specific hierarchy / adapter-only
  strategies / strategies on raw framework request with runtime
  dispatch). Cross-adapter pattern alignment table comparing Django
  adapter and SA adapter symmetries documented. Empirical evidence
  cross-referenced across Tareas 4B.0 through 4B.5. Materialized in
  Tarea 4B.6.

### Notes

- DR-027 remains SKIPPED en the ledger per the Sub-fase 3B scope
  refinement; DR materialization continues monotonically from DR-028
  (Sub-fase 4A) through DR-036 (Sub-fase 4B). Ledger immutability is
  project canon.
- Phase 3A event-based enforcement reuse continues -- zero new event
  handlers introduced en Sub-fase 4B (the cross-adapter strategy
  layer is orthogonal to the SA event handler dispatch model).
- BLOCKER #30 (Phase 2B Django-bound strategies) deferral closed
  empirically end-to-end in Tarea 4B.5: 8 integration tests
  demonstrate the same strategy class instance + ``resolve_strategy``
  output extract identical tenants via both ``DjangoRequestAdapter``
  and ``AsgiRequestAdapter``.
- Django adapter retains its separate ``resolve_strategy()`` raising
  ``ImproperlyConfigured`` per the Phase 2B / DPRJ-2 contract; cross-
  adapter consumers use the core factory raising ``ValueError``.
  Coexistence is intentional; future consolidation (post-1.0) may
  merge them via an adapter-side error-translation shim.
- Two ``TenantExtractionError`` classes coexist: the cross-adapter
  core (``tenantshield.strategies.TenantExtractionError``,
  kwarg-only) and the Django adapter
  (``tenantshield.adapters.django.exceptions.TenantExtractionError``,
  positional). Django strategy subclasses translate core errors to
  the Django-namespaced class via ``from exc`` chaining (Rule 62).
- Rule 60 applied a second time in project history: ADR-0008 cross-
  references updated en mismo commit batch que ADR-0010
  materialization (Tarea 4B.6). First application was Tarea 0.2
  housekeeping (ADR-0008 DR-026 framing correction + DR-027 orphan
  cleanup).
- Phase 4 widening backlog status unchanged: ``pytest-cov`` widened
  in Tarea 4.0; 4 monitor items (django ecosystem + mypy) deferred
  to Phase 4 closure pin audit per Rule 61.

## [0.4.0-alpha.0] -- 2026-05-17

### Sub-fase 4A summary

Sub-fase 4A delivers the asynchronous SQLAlchemy adapter surface,
closing Decision 2-A's deferral from Sub-fase 3B. AsyncSession adopters
gain parallel lifecycle helpers (`AsyncSessionScope` +
`bind_async_session_to_tenant`), dual-mode resolver capability in
`TenantSessionMiddleware` (sync or async resolver, transparent
dispatch), and an AsyncSession-native FastAPI example replacing the
Phase 3 sync + `run_in_threadpool` pattern (Decision 7-A).

Architectural payoff of Phase 3A's event-based enforcement choice:
zero new event handlers were required. SQLAlchemy
`AsyncSession.sync_session_class = Session` routes async ops through
the existing Phase 3A handler dispatch, empirically verified
end-to-end across all enforcement paths (write + read).

### Acceptance gates (8/8 met)

- 412 library tests passing on canonical Python 3.13 + SA 2.0.49 +
  aiosqlite 0.22.1 (45 new tests added in Sub-fase 4A).
- 16 example tests passing (5 CLI + 5 Flask + 6 FastAPI async)
  isolated from main library suite.
- Library coverage 99.91% (gate >=95%); all productive SA adapter
  modules at 100% lines + branches (`async_lifecycle.py` 100%,
  `middleware.py` 100% post-extension, `events.py` 100% via Rule 28
  pragma per Tarea 0.1).
- mypy strict + pyright clean + ruff clean + 13/13 pre-commit hooks
  green.
- Public surface stable + extended: 27 canonical imports (Core 4 +
  Django adapter 4 + Strategies 6 + DRF adapter 4 + SA adapter 9
  (+`AsyncSessionScope` +`bind_async_session_to_tenant`)).
- 9 ADRs documenting architectural decisions (0001-0009).
- 31 Decision Records (DR-001 through DR-027 skipped + DR-028..032
  added in Sub-fase 4A).
- All sub-fase tags preserved (`v0.3.0-alpha.0`, `v0.3.0-alpha.1`,
  `v0.4.0-alpha.0`).
- Phase 3A handler reuse confirmed empirically (write + read paths)
  with zero new event handler code.

### Added

- `tenantshield.adapters.sqlalchemy.AsyncSessionScope` async context
  manager. Mirrors `SessionScope` parameter parity (`tenant`,
  `resolve_tenant`) and fall-through / mutual-exclusivity semantics.
  Implemented as `@asynccontextmanager`-decorated function wrapping
  `tenantshield.atenant_scope`. Decision 3-A.
- `tenantshield.adapters.sqlalchemy.bind_async_session_to_tenant`
  async explicit tenant binding helper. Mirrors
  `bind_session_to_tenant` parameter parity (single positional
  `tenant`, raise on `None` / empty). Composable with
  `AsyncSessionScope` for nested binding semantics (inner-override,
  outer-restore-on-exit). Decision 3-A.
- `TenantSessionMiddleware` (ASGI) dual-mode resolver support.
  Resolver may return either `TenantId | str | None` (Phase 3B
  precedent) or `Awaitable[TenantId | str | None]` (Sub-fase 4A
  extension). Middleware auto-awaits via `inspect.iscoroutine`.
  Backward compatibility preserved: existing sync resolvers
  unchanged. Decision 3-A.
- AsyncSession-native FastAPI example
  (`examples/02_sqlalchemy/fastapi/`) replacing the Phase 3 sync +
  `run_in_threadpool` pattern (Decision 7-A). Demonstrates dual-mode
  resolver in the same example (default `app` sync resolver,
  `strict_app` async resolver). 6 end-to-end tests via FastAPI
  `TestClient`.
- `aiosqlite>=0.22,<1.0` dev dependency (Rule 32 eligible 145 days
  stable at pin selection). Used for AsyncSession integration tests
  and the FastAPI async example.

### Changed

- `pytest-cov` pin widened to `<8.0` and functionally upgraded to
  7.1.0 (Tarea 4.0, Rule 32 + BLOCKER #31 Option β resolution
  introducing pin-widening operational discipline distinguishing
  symbolic widening from functional adoption).
- Scratch artifacts under `_scratch_*` excluded from `ruff` via
  `[tool.ruff].extend-exclude` (Tarea 4A.1, BLOCKER #32 Option β
  resolution preserving 4A.0 GO directive to keep empirical
  exploration scratch files locally).

### Decision Records

- **DR-028** -- Async ContextVar propagation invariants for the SA
  adapter. Sync `ContextVar` set in async code is visible across
  `await` boundaries within the same task (asyncio per-task
  `copy_context()` semantics, Rule 55 reconfirms). Concurrent
  `asyncio.gather` tasks are isolated; binding in one task does not
  leak to others. Empirically validated in Tarea 4A.0 Scenarios 1 + 2
  and reconfirmed via Tarea 4A.5 dual-mode middleware tests.
- **DR-029** -- AsyncSession mapper event dispatch reuses Phase 3A
  handlers. `event.listen(cls, "before_insert", ...)` (and update /
  delete) fires under `await AsyncSession.flush()` because SQLAlchemy
  dispatches events at the underlying sync engine flush layer; no
  async-specific listeners required. Empirically validated in Tarea
  4A.0 Scenario 4 and reconfirmed end-to-end in Tarea 4A.3 (3 write
  enforcement scenarios + AsyncSessionScope integration + cross-tenant
  blocking).
- **DR-030** -- AsyncSession `do_orm_execute` dispatch reuses Phase 3A
  read filtering. The session-level event registered on `Session`
  fires for `await AsyncSession.execute(select(...))` because
  `AsyncSession.sync_session_class = Session`; the same handler
  injects `with_loader_criteria` filtering transparently. Empirically
  validated in Tarea 4A.0 Scenario 3 and reconfirmed end-to-end in
  Tarea 4A.4 (9 read filtering scenarios).
- **DR-031** -- ASGI `TenantSessionMiddleware` dual-mode resolver
  support. Resolver returns either synchronous `TenantId | str | None`
  or asynchronous `Awaitable[TenantId | str | None]`. Middleware
  invokes resolver, dispatches via `inspect.iscoroutine`, and awaits
  when needed. Backward compatibility preserved: existing sync
  resolvers continue working with no signature widening required
  (the `Callable[..., Any]` type alias already permits dual-mode at
  the type-system level). WSGI middleware remains sync-only by design.
  Materialized in Tarea 4A.5.
- **DR-032** -- Async/sync coexistence in the same process. Single
  ContextVar binding shared across sync `tenant_scope` and async
  `atenant_scope` flavors. `asyncio.to_thread` propagates context to
  worker threads, enabling sync utilities called from async code (and
  vice versa via `asyncio.run`) to observe the active tenant. Phase 3A
  enforcement applies regardless of which flavor executes the DB
  operation. Empirically validated in Tarea 4A.0 Scenario 7 and
  formalized as integration tests in Tarea 4A.7.

### Architectural Decision Records

- **ADR-0009** -- AsyncSession adapter architecture. Phase 4A
  introduces parallel async lifecycle helpers + dual-mode resolver
  middleware leveraging Phase 3A event handler reuse via
  `AsyncSession.sync_session_class`. Three alternatives rejected with
  rationale: parallel async-specific event handlers (Phase 3A reuse
  preferred; dispatch divergence risk avoided), `SessionScope`
  dual-mode magic (Decision 3-A explicitly chose parallel helpers),
  async-only resolver-only middleware (backward compatibility
  preserved). Five empirical pillars documented with cross-references
  to Tarea 4A.0-4A.7 scenarios + tests. Materialized in Tarea 4A.8
  (Sub-fase 4A closure).

### Notes

- DR-027 was skipped in Sub-fase 3B per scope refinement; the DR
  ledger preserves the skipped entry for historical accuracy and
  continues with DR-028 forward. Ledger immutability is project canon.
- Phase 3 architectural design choice (event-based enforcement,
  ADR-0007) pays compound dividends in Phase 4: zero new event
  handlers needed for AsyncSession adoption. Adopters with existing
  `@tenant_aware`-decorated models require no code changes to benefit
  from Phase 4A AsyncSession support.
- Phase 4A widening backlog status: pytest-cov widened in Tarea 4.0;
  4 monitor items (django ecosystem + mypy) deferred to Phase 4
  closure pin audit per Rule 61.

## [0.3.0-alpha] -- 2026-05-16

### Phase 3 summary

Phase 3 of TenantShield delivers complete SQLAlchemy adapter coverage
across the ORM lifecycle plus framework integration layer. The release
closes three sub-phases:

- **Sub-fase 3A (`v0.3.0-alpha.0`)** -- enforcement core with the
  `@tenant_aware` decorator, mapper event-based write enforcement
  (`before_insert`/`before_update`/`before_delete`), `do_orm_execute`
  read filtering with `with_loader_criteria` injection, and
  documented bypass surface for raw SQL (DR-023), bulk operations
  (DR-024), and flush timing (DR-025).
- **Sub-fase 3B (`v0.3.0-alpha.1`)** -- session middleware layer:
  `SessionScope` context manager + `bind_session_to_tenant` helper
  (framework-agnostic core) + `TenantSessionMiddleware` (ASGI) +
  `TenantSessionMiddlewareWSGI` (WSGI) with `yield from` generator
  pattern (Rule 54) + opt-in strict enforcement via
  `on_missing_tenant='raise'` (DR-026).
- **Sub-fase 3C (this release)** -- three runnable examples
  demonstrating adapter usage across FastAPI (ASGI), Flask (WSGI),
  and framework-agnostic CLI contexts. Validates Sub-fase 3B
  mock-based middleware tests against real frameworks
  (Decision 8-A acceptance gate).

### Acceptance gates (8/8 met)

- 367 library tests passing on canonical Python 3.13 + SA 2.0.49.
- 16 example tests passing (6 FastAPI + 5 Flask + 5 CLI) isolated
  from main library suite via `testpaths = ["tests"]`.
- Library coverage 99.70% global (gate >=95%). All Phase 3
  productive SA adapter modules at 100% lines + branches except
  `events.py` (97.62%, pre-existing entity-is-None defensive
  null-check accepted per 3A.5 Option A).
- mypy strict + pyright clean + ruff clean + 13/13 pre-commit hooks
  green.
- Public surface stable: 25 canonical imports verified working
  (Core 4 + Django adapter 4 + Strategies 6 + DRF adapter 4 +
  SA adapter 7).
- 8 ADRs documenting architectural decisions (0001-0008).
- 26 Decision Records added across the project (DR-001 through
  DR-026). Phase 3 added DR-021 through DR-026.
- All sub-fase tags preserved (`v0.3.0-alpha.0`, `v0.3.0-alpha.1`).
- 3 runnable examples shipped, schema byte-identical across all
  three (cross-example consistency rigorous).

### Added (Sub-fase 3C)

- `examples/02_sqlalchemy/` runnable examples directory with shared
  `README.md` overview documenting sync/async boundary for SA
  adapter (sync-only in Phase 3; `AsyncSession` deferred to
  Phase 4+) and Phase 2B strategies non-use rationale (BLOCKER #30
  resolution: SA middleware accepts callable resolvers only).
- `examples/02_sqlalchemy/fastapi/` -- FastAPI ASGI integration:
  - `TenantSessionMiddleware` integration via
    `app.add_middleware(...)`.
  - Callable resolver extracting `X-Tenant-ID` from ASGI scope.
  - Sync route handler (recommended) + async route handler with
    `starlette.concurrency.run_in_threadpool` (correct async
    pattern; never call sync `Session()` inside `async def` without
    threadpool).
  - Strict mode opt-in via separate `strict_app` instance with
    `on_missing_tenant='raise'`.
  - 6 end-to-end tests via FastAPI `TestClient`.
- `examples/02_sqlalchemy/flask/` -- Flask WSGI integration:
  - `TenantSessionMiddlewareWSGI` integration via
    `app.wsgi_app = TenantSessionMiddlewareWSGI(...)`.
  - Callable resolver extracting `HTTP_X_TENANT_ID` from WSGI
    environ.
  - Application factory pattern (`create_app`, `create_strict_app`)
    for Flask CLI deployment and test fixture isolation.
  - Strict mode opt-in via separate `create_strict_app()` factory.
  - 5 end-to-end tests via Flask test client.
- `examples/02_sqlalchemy/cli/` -- framework-agnostic CLI:
  - Direct `SessionScope` usage for batch operations.
  - `bind_session_to_tenant` explicit helper.
  - Nested composition (outer `SessionScope` + inner
    `bind_session_to_tenant` override; outer restored on inner
    exit).
  - argparse subcommands: `seed`, `report --tenant <name>`, `sweep`,
    `nested`. Auto-seed-before-non-seed command guarantees data
    availability for demo invocations.
  - Idempotent `seed_demo_data()` via raw SQL `DELETE` (cites
    Rule 51 in adopter-facing code).
  - 5 end-to-end tests via direct `main()` invocation + `capsys`.

### Architecture milestones reached

- SQLAlchemy 2.0+ adapter ships with complete enforcement
  semantics: writes auto-inject `tenant_id`, cross-tenant writes
  reject via mapper events, reads filter by tenant via
  `do_orm_execute`. Documented bypass surface (raw SQL,
  bulk operations) makes adopter escape hatches explicit.
- Framework-agnostic session lifecycle binding via `SessionScope`
  plus `bind_session_to_tenant`; ASGI + WSGI middleware wrappers
  preserve scope semantics across framework boundaries (Rules
  54-55).
- Cross-adapter parameter naming alignment with Django adapter
  (`on_missing_tenant` consistent across SA + Django middleware;
  semantic divergence acknowledged: Django default `'raise'`, SA
  default `'allow_unrestricted'`, per DR-026 rationale).
- Three runnable examples validate Sub-fase 3B mock-based
  middleware tests against real ASGI/WSGI frameworks
  (Decision 8-A acceptance gate closed by Sub-fase 3C).
- Phase 2B strategies empirically confirmed Django-bound during
  Sub-fase 3B; cross-adapter strategy unification formally
  deferred (BLOCKER #30 Path c resolution; revisit Phase 4+).
- Empirical methodology refinements transmitted forward via
  Rules 49-55 (absorbed in post-3A + post-3B consolidations):
  - **Rule 49**: Pattern P1 version bump policy
    (`__version__` bumps only at Phase root tag).
  - **Rule 50**: PEP 561 verification via `py.typed` marker file.
  - **Rule 51**: bulk write test verification via raw SQL or
    outside-scope load.
  - **Rule 52**: `with_loader_criteria` requires static SQL
    expression, never lambda (cache caveat).
  - **Rule 53**: `TenantId` NewType normalization via
    `TenantId(str(value))`.
  - **Rule 54**: WSGI middleware uses `yield from` for
    streaming-safe scope.
  - **Rule 55**: sync `ContextVar` visible across async `await`
    boundaries via asyncio per-task `copy_context()`.

### Version trajectory

- `__version__` bumped `0.2.0a0` -> `0.3.0a0` at Phase 3 root tag
  per Rule 49 (Pattern P1). First instance of Phase root version
  bump in Phase 3; pattern coherent with Phase 2 closure precedent
  (commit `a5f30b3`).
- Sub-fase tags (`v0.3.0-alpha.0`, `v0.3.0-alpha.1`) preserved
  `__version__ = 0.2.0a0` per Rule 49.

### Phase 3 -> Phase 4 transition

Phase 4 scope TBD. Anticipated candidates per Sub-fase 3B kickoff
Decision 2-A and BLOCKER #30 deferrals:

- `AsyncSession` adapter support (deferred per Decision 2-A in
  Sub-fase 3B kickoff).
- Cross-adapter strategy unification (deferred per BLOCKER #30
  Path c, Sub-fase 3B).
- Additional ORM adapters or expanded enforcement primitives.

Phase 4 kickoff message will materialize scope decisions on next
architectural turn.

### See also

- See the `[0.3.0-alpha.0]` section below for full Sub-fase 3A
  details (enforcement core: decorator + mapper events +
  `do_orm_execute` + bypass semantics + flush timing).
- See the `[0.3.0-alpha.1]` section below for full Sub-fase 3B
  details (session middleware: `SessionScope` +
  `bind_session_to_tenant` + ASGI + WSGI middleware + strict mode).
- `docs/adr/0006-sqlalchemy-2-0-only.md` (SA 2.0+ scope rationale).
- `docs/adr/0007-event-based-enforcement.md` (enforcement
  architecture).
- `docs/adr/0008-middleware-lifecycle-design.md` (middleware
  two-layer design pattern; ContextVar-based binding;
  callable-only resolver).

## [0.3.0-alpha.1] -- 2026-05-16

Sub-fase 3B complete -- SQLAlchemy session middleware. Framework-
agnostic session lifecycle binding via `SessionScope` context manager
and `bind_session_to_tenant` helper, plus ASGI/WSGI middleware classes
(`TenantSessionMiddleware` / `TenantSessionMiddlewareWSGI`) with
optional strict enforcement via `on_missing_tenant='raise'`
configuration.

### Added

- `tenantshield.adapters.sqlalchemy.SessionScope` context manager
  with direct tenant binding or callable-resolver pattern. Fall-
  through semantics on missing scope per DR-022 standalone behavior.
- `tenantshield.adapters.sqlalchemy.bind_session_to_tenant` explicit
  tenant binding helper. Composable with `SessionScope` for nested
  binding semantics (inner-override, outer-restore-on-exit).
- `tenantshield.adapters.sqlalchemy.TenantSessionMiddleware` ASGI
  middleware. Wraps inner app with tenant scope established via
  `SessionScope` internally. ContextVar copy semantics preserve
  scope across `await` boundaries (asyncio per-task context copy).
  HTTP-only binding; websocket / lifespan scopes pass through.
- `tenantshield.adapters.sqlalchemy.TenantSessionMiddlewareWSGI`
  WSGI middleware. Generator-based pattern (`yield from`) preserves
  `SessionScope` during full response body iteration (critical for
  streaming responses; naive `return` pattern exits scope before
  iteration begins).
- `on_missing_tenant` middleware configuration parameter accepting
  `'allow_unrestricted'` (default; backwards-compatible fall-through)
  or `'raise'` (strict mode raising `MissingTenantContextError` when
  resolver returns `None`). Applies to both ASGI and WSGI variants.

### Decision Records

- **DR-026** -- Middleware-managed strict enforcement for SQLAlchemy
  adapter. Two-mode behavior on missing tenant:
  `on_missing_tenant='allow_unrestricted'` (default, fall-through per
  DR-022 backwards-compat) or `on_missing_tenant='raise'` (strict,
  `MissingTenantContextError`). Applies to both `TenantSessionMiddleware`
  (ASGI) and `TenantSessionMiddlewareWSGI` (WSGI). Materializes the
  deferred-from-Sub-fase-3A DR-022 strict-behavior promise per
  Decision 4-C from Phase 3B kickoff. Cross-adapter naming alignment
  with Django adapter `TenantContextMiddleware` (Sub-fase 2B
  precedent); semantic divergence acknowledged -- Django default is
  `'raise'` (no standalone path); SA default is `'allow_unrestricted'`
  (preserves DR-022 standalone fall-through). Materialized in Tarea
  3B.5.

### Architectural Decision Records

- **ADR-0008** -- Middleware lifecycle design pattern for SQLAlchemy
  adapter. Two-layer architecture: `lifecycle.py` core (`SessionScope`
  + `bind_session_to_tenant`) + `middleware.py` framework integration
  (`TenantSessionMiddleware` ASGI + `TenantSessionMiddlewareWSGI`
  WSGI). ContextVar-based binding (Decision 5-B from Phase 3B
  kickoff). Callable-only resolver pattern (Decision 3 revised per
  BLOCKER #30: Phase 2B strategies empirically Django-bound;
  cross-adapter strategy unification deferred to dedicated future
  sub-fase or Phase 4). Three alternatives rejected with rationale:
  SA Session subclassing (breaks framework-agnostic design), SA
  event-listener binding (lazy-begin timing unreliable; couples
  scope to SA transaction lifecycle), Protocol abstraction for Phase
  2B strategy reuse (scope expansion + Django adapter regression
  risk). Materialized in Tarea 3B.2 evidence-based after empirical
  validation in Tareas 3B.0-re + 3B.1.

### Acceptance gates (Sub-fase 3B)

- 367 tests passing on canonical Python 3.13 + SA 2.0.49 (+43 vs
  Sub-fase 3A closure's 324).
- Coverage 99.70% global (gate `>= 95%`; improved +0.03 vs Sub-fase
  3A closure's 99.67%). Both Sub-fase 3B productive modules
  (`lifecycle.py`, `middleware.py`) at 100% lines + branches.
  `events.py` retains 97.62% (pre-existing entity-is-None defensive
  null-check, accepted per 3A.5 Option A).
- mypy strict + pyright clean + ruff clean + 13/13 pre-commit hooks
  green.
- Public surface stable: 25 canonical imports (Phase 2's 18 + SA
  adapter's 7; +4 from Sub-fase 3B: `SessionScope`,
  `bind_session_to_tenant`, `TenantSessionMiddleware`,
  `TenantSessionMiddlewareWSGI`).
- 2 new SA adapter modules at 100% coverage (`lifecycle.py` 31 stmts
  + `middleware.py` 43 stmts).
- 1 Decision Record added (DR-026 strict enforcement).
- 1 Architectural Decision Record added (ADR-0008 middleware
  lifecycle design).

### Architecture milestones reached

- SQLAlchemy session lifecycle binding complete (framework-agnostic
  `SessionScope` + explicit `bind_session_to_tenant` helper).
- ASGI + WSGI middleware classes shipped with optional strict
  enforcement. Adopter framework targets supported: FastAPI,
  Starlette, Flask, Django (WSGI mode), Gunicorn, Uvicorn.
- Cross-adapter parameter naming alignment with Django adapter
  (`on_missing_tenant` consistent across SA + Django middleware).
- Empirical methodology refinements:
  - ContextVar copy semantics across `await` boundaries verified
    (asyncio per-task `copy_context()`).
  - WSGI iterable scope semantics: generator pattern (`yield from`)
    canonical for streaming-safe middleware; naive `return` pattern
    exits scope before iteration (critical empirical finding in
    Tarea 3B.4).
  - Phase 2B strategies empirically confirmed Django-bound;
    cross-adapter strategy unification deferred per BLOCKER #30.
  - `TenantId` NewType isinstance limitation (canonical
    normalization via `TenantId(str(...))`; discovered in Tarea
    3B.1).

### See also

- `docs/adr/0006-sqlalchemy-2-0-only.md`
- `docs/adr/0007-event-based-enforcement.md`
- `docs/adr/0008-middleware-lifecycle-design.md`
- DR-022 (read enforcement fall-through; resolved by DR-026 strict-
  mode opt-in for middleware-wrapped contexts).

## [0.3.0-alpha.0] -- 2026-05-15

Sub-fase 3A complete -- SQLAlchemy ORM enforcement core. Multi-tenant
isolation for SQLAlchemy 2.0+ declarative models via mapper-scoped
write events, session-scoped read filtering, and documented bypass
semantics for raw SQL and bulk operations.

### Added

- `tenantshield[sqlalchemy]` optional dependency extra declaring
  `sqlalchemy>=2.0,<3.0`. Foundation for the SQLAlchemy adapter.
- `tenantshield.adapters.sqlalchemy` module with public surface:
  - `tenant_aware` decorator for SQLAlchemy declarative model classes.
    Validates `tenant_id` column presence at class-definition time
    (fail-fast `ConfigurationError` if missing) and registers mapper
    event listeners for write enforcement.
  - `MissingTenantContextError` re-exported from
    `tenantshield.exceptions` for ergonomic adapter-local import.
  - `CrossTenantAccessError` re-exported from
    `tenantshield.exceptions` for ergonomic adapter-local import.
- SQLAlchemy adapter modules: `decorator.py`, `events.py`,
  `exceptions.py`. All at 97.6-100% coverage.

### Decision Records

- **DR-021** -- Write enforcement via mapper-scoped events
  (`before_insert`, `before_update`, `before_delete`). Auto-injects
  `tenant_id` on INSERT from the active scope when the attribute is
  unset; raises `CrossTenantAccessError` on cross-tenant write
  attempts (mismatched explicit `tenant_id` vs active scope) and
  `MissingTenantContextError` when no scope is active. Materialized
  incrementally in Tareas 3A.3 (INSERT, auto-inject path) and 3A.4
  (UPDATE + DELETE, validation-only paths).
- **DR-022** -- Read enforcement via session-scoped `do_orm_execute`
  event with `with_loader_criteria` injection. Filters ORM SELECT
  statements on tenant-aware models by the active scope. Fall-through
  on missing scope (no filtering applied) matches kickoff §3 design;
  stricter raise-on-missing behavior is provided by middleware in
  Sub-fase 3B. Uses a static SQL expression rather than a lambda
  because SQLAlchemy caches loader-criteria lambdas by body and
  ignores closure variables (architectural gotcha documented in
  ADR-0007). Materialized in Tarea 3A.5.
- **DR-023** -- SQLAlchemy raw SQL via `text()` bypasses ALL tenant
  enforcement layers. Raw statements skip `do_orm_execute` filter
  injection (handler guards on `is_orm_statement`) and skip
  mapper-scoped events because text statements do not trigger mapper
  machinery. This is an intentional architectural constraint matching
  Django adapter's `_base_manager` semantics: raw SQL is the
  documented escape hatch for adopter operations requiring full
  control. Adopters using `session.execute(text("..."))` inherit
  complete responsibility for tenant coherence. Materialized in
  Tarea 3A.7 with empirical evidence + 8 test cases documenting
  bypass behavior. See ADR-0007 consequences section.
- **DR-024** -- SQLAlchemy bulk operations bypass mapper-scoped
  events. `session.execute(insert(Foo).values([...]))`,
  `session.execute(update(Foo).where(...).values(...))`, and
  `session.execute(delete(Foo).where(...))` bypass the
  `before_insert`, `before_update`, and `before_delete` events
  respectively. This is SQLAlchemy's documented behavior for
  performance reasons. Consequence: tenant enforcement on write
  paths is NOT applied to bulk operations. Adopters using bulk
  patterns must manually validate tenant coherence. Read operations
  via `session.execute(select(Foo))` are still filtered regardless
  of bulk or individual fetch pattern. Materialized in Tarea 3A.6
  with empirical evidence + 5 test cases.
- **DR-025** -- SQLAlchemy adapter enforcement fires at flush time,
  not at `session.add()` / `session.delete()` time. Implications:
  tenant scope must be active at flush (whether explicit
  `session.flush()`, autoflush before a query, or implicit flush
  during `session.commit()`); scope changes between `add()` and
  `flush()` use the scope active AT FLUSH TIME (auto-injection
  reflects flush-time scope, not add-time scope); autoflush (default
  in SA 2.0) triggers events before SELECT queries with pending
  writes; expunged instances (`session.expunge()`) do not fire
  events. Adopter guidance: keep tenant scope active throughout
  session operations, not only during instance construction. Pattern
  paralelo a Django adapter's signal firing at `model.save()` time;
  SA adapter's flush-time firing matches SA's session lifecycle.
  Together with DR-021 (write enforcement) and DR-022 (read
  enforcement), DR-025 establishes the complete timing semantics of
  the adapter. Materialized in Tarea 3A.9 with empirical evidence +
  7 test cases across flush, autoflush, commit, and expunge timing
  points.

### Architectural Decision Records

- **ADR-0006** -- SQLAlchemy 2.0+ only; drops 1.4 support. Single
  major-version target simplifies adapter implementation; PEP 561
  inline typing in SA 2.0+ eliminates need for a parallel stubs
  package. Materialized in Tarea 3A.0.
- **ADR-0007** -- Event-based enforcement for SQLAlchemy adapter.
  Materializes Decision 4-A from PHASE_3A_KICKOFF.md. Three event
  mechanisms compose tenant enforcement:
  `before_insert`/`before_update`/`before_delete` mapper-scoped
  events for writes; `do_orm_execute` session-scoped event for
  reads via `with_loader_criteria` injection (static SQL expression,
  not lambda -- SA caches loader-criteria lambdas by body and ignores
  closure variables). Reads fall through on missing scope; stricter
  raise-on-missing behavior provided by middleware in Sub-fase 3B.
  Materialized in Tarea 3A.5.

### Acceptance gates (Sub-fase 3A)

- 324 tests passing on canonical Python 3.13 / SA 2.0.49.
- Coverage 99.67% global (gate `>= 95%`). 0.21 points below kickoff
  §6 99.88% aspirational target due to 1 missing defensive branch in
  `do_orm_execute` handler (`entity is None` edge case in
  `column_descriptions` iteration; hard to trigger via SA's public
  API). Documented gap; accepted per Tarea 3A.5 Option A.
- mypy strict + pyright clean + ruff clean + 13/13 pre-commit hooks
  green.
- Public surface stable: 21 canonical imports verified working
  (Phase 2's 18 + SA adapter's 3).
- 5 SA adapter modules at 97.6-100% coverage
  (`__init__.py`, `decorator.py`, `events.py`, `exceptions.py`,
  plus `__init__.py` re-exports).
- 5 Decision Records added (DR-021 through DR-025) documenting the
  complete enforcement surface (writes + reads + bypass semantics +
  timing).
- 2 Architectural Decision Records added (ADR-0006, ADR-0007)
  documenting SA 2.0+ pin and event-based enforcement strategy.

### Architecture milestones reached

- SQLAlchemy ORM enforcement complete: writes (auto-inject + reject
  cross-tenant) and reads (filter by scope) covered by event-based
  architecture.
- Cross-adapter coherence with Django adapter preserved: same
  exception hierarchy (`MissingTenantContextError`,
  `CrossTenantAccessError`), same `operation` identifier format
  (`<event>.<Model>`), same bypass-as-escape-hatch semantics for
  out-of-ORM operations.
- Empirical methodology refinement: lambda caching caveat in
  `with_loader_criteria` documented as architectural gotcha
  (ADR-0007); future SQLAlchemy adapter work uses static SQL
  expressions, not closure-capturing lambdas.

### See also

- `docs/adr/0006-sqlalchemy-2-0-only.md`
- `docs/adr/0007-event-based-enforcement.md`

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
