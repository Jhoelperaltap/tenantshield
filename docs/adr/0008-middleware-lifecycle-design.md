# ADR-0008 -- Middleware lifecycle design pattern for SQLAlchemy adapter

**Status:** Accepted.
**Date:** 2026-05-15.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.
**Related:** Decision 3 (revised post-BLOCKER #30), Decision 5-B
(ContextVar-based binding), DR-022 (read enforcement fall-through),
DR-026 (TBD: strict middleware behavior in Tarea 3B.5),
DR-027 (TBD: middleware-specific decision records, Tareas 3B.3-5).

## Context

Sub-fase 3B extends the SQLAlchemy adapter with session lifecycle
management + ASGI/WSGI middleware classes. Three architectural
questions emerged:

1. How should adopters bind tenant scope to SA Session operations?
2. Should TenantShield reuse Phase 2B Django strategies for tenant
   resolution, or define a new abstraction?
3. How should middleware compose with SA's existing Session
   lifecycle (begin/commit/rollback events)?

## Decision

The SQLAlchemy adapter implements a two-layer lifecycle architecture:

### Layer 1 -- Core abstractions (`lifecycle.py`)

- `SessionScope`: context manager supporting direct tenant binding
  OR callable resolver pattern.
- `bind_session_to_tenant`: helper for direct tenant binding only.

Both wrap `tenantshield.tenant_scope` internally. NO SQLAlchemy
`Session` subclassing; NO event listener registration. ContextVar-
based binding (Decision 5-B from Phase 3B kickoff).

### Layer 2 -- Framework integration (`middleware.py`)

- `TenantSessionMiddleware`: ASGI/WSGI middleware classes that
  wrap request handling with a `SessionScope` block. Materialization
  in Tareas 3B.3 (ASGI) and 3B.4 (WSGI).
- Tenant resolution via callable parameter: `resolve_tenant:
  Callable[[Any], TenantId | None]`.

NO reuse of Phase 2B `TenantExtractionStrategy` classes -- those
are Django-bound (use `request.META`, `request.get_host()`).
Cross-adapter strategy unification deferred per BLOCKER #30
resolution (Sub-fase 3B Tarea 3B.0 empirical findings).

## Alternatives considered

### Alternative A -- SA Session subclassing for tenant binding

Define `TenantBoundSession(Session)` subclass. Override `__init__`
to bind tenant context; adopters use
`sessionmaker(class_=TenantBoundSession)`.

**Rejected because:**

- Forces inheritance, breaking framework-agnostic design.
- Incompatible with `sessionmaker`, `scoped_session`,
  `AsyncSession` factories that adopters already use.
- Complicates SA Session subclassing landscape (vendor-managed
  attributes, future SA API changes).
- ContextVar-based approach achieves same semantics without
  inheritance.

### Alternative B -- SA event listener for tenant binding

Register `Session` `after_begin`/`before_commit` event listeners.
Bind tenant scope at transaction begin; unbind at commit.

**Rejected because:**

- Empirical finding (Tarea 3B.0-re Scenario 1): SA uses lazy-begin
  semantics. Transaction begins on first flush, NOT on `Session()`
  instantiation. Event firing order:
  `before_commit -> before_flush -> after_begin -> after_flush ->
  after_commit`. Event timing makes scope binding unreliable.
- Couples tenant scope to SA transaction lifecycle (begin/commit/
  rollback) when scope should map to request lifecycle (broader).
- Multiple transactions per request would each rebind scope --
  surprising adopter semantics.

### Alternative C -- Phase 2B strategy reuse via Protocol abstraction

Define neutral `RequestProtocol` interface; adapt Phase 2B
strategies to use it. Multi-framework adopters get cross-adapter
strategy coherence.

**Rejected per BLOCKER #30 resolution:**

- Phase 2B strategies (`HeaderStrategy`, `JWTStrategy`,
  `SubdomainStrategy`) use Django-specific APIs internally
  (`request.META`, `request.get_host()`). Empirically verified
  3/4 strategies Django-bound.
- Refactoring to neutral Protocol expands Sub-fase 3B scope by
  ~3-4 tareas.
- Risk of Django adapter test regression on in-place modification
  (Django adapter at 99.81% coverage; modifications carry risk).
- Two-framework adopter use case is edge.
- Callable resolver pattern adequately covers FastAPI / Starlette /
  Flask / Werkzeug integration; adopters write 1-10 LOC.

Future cross-adapter strategy unification deferred to dedicated
sub-fase or Phase 4.

## Consequences

### Positive

- **Framework-agnostic core:** `SessionScope` and
  `bind_session_to_tenant` usable in any context (CLI, workers,
  tests, web requests).
- **Composable with SA patterns:** works with arbitrary `Session`,
  `sessionmaker`, `scoped_session` factories. Empirically validated
  (Tarea 3B.0-re Scenario 4).
- **Thread-safe via ContextVar:** Python `contextvars.ContextVar`
  thread-isolated by default. Critical for multi-threaded WSGI
  workers. Empirically validated.
- **Exception transparency:** standard try/finally semantics
  propagate exceptions to caller without modification. Decision 6-A
  materialized.
- **Composition with Phase 1 core:** thin wrapper around
  `tenant_scope` preserves Phase 1 invariants.
- **Nested binding works:** `bind_session_to_tenant` inside
  `SessionScope` produces inner-override semantics; outer restored
  on inner exit. Empirically validated in Tarea 3B.2.

### Negative

- **Adopters write resolver callables:** ASGI/WSGI middleware
  requires adopter-provided callable to extract tenant from request.
  ~1-10 LOC overhead vs Django adapter's strategy classes.
- **Cross-adapter strategy fragmentation:** Django adapter uses
  `TenantExtractionStrategy`; SA adapter uses callable resolver.
  Multi-framework adopters maintain separate extraction code per
  adapter. Acceptable tradeoff per BLOCKER #30 resolution.
- **No automatic session detection:** `SessionScope` does NOT
  inspect for active SA Sessions or rebind based on Session
  lifecycle. Adopters responsible for scope-session timing.
- **`@tenant_aware` decorator still required:** `SessionScope`
  binds ContextVar but enforcement only fires on
  `@tenant_aware`-decorated models. SessionScope alone provides
  NO enforcement on undecorated models. Adopters relying on
  `SessionScope` must decorate their tenant-aware models.

### Cross-adapter pattern alignment

| Aspect | Django adapter | SQLAlchemy adapter |
|---|---|---|
| Tenant binding mechanism | `TenantContextMiddleware` | `SessionScope` + `TenantSessionMiddleware` |
| Binding scope | request (Django) | request (ASGI/WSGI) OR context manager |
| Tenant resolution | `TenantExtractionStrategy` (4 strategies) | Callable resolver (adopter-provided) |
| Enforcement layer | Manager + queryset filtering | Mapper + session events |
| Scope cleanup | Middleware `__call__` exit | ContextVar reset on context exit |
| Exception handling | Standard middleware semantics | `try/finally` transparency |

## Empirical evidence

Sub-fase 3B Tareas 3B.0-re + 3B.1 + 3B.2 empirically validated:

- ContextVar reset on exception (3/3 scenarios; Tarea 3B.0-re).
- `scoped_session` independence from ContextVar (3/3 scenarios;
  Tarea 3B.0-re).
- SA Session lifecycle event timing (lazy-begin observed; Tarea
  3B.0-re Scenario 1).
- Multiple sessions per scope sharing tenant context (Tarea
  3B.0-re Scenario 5).
- Phase 2B strategy Django binding (3/4 strategies confirmed;
  Tarea 3B.0).
- `SessionScope` empirical end-to-end with SA adapter (3/3
  scenarios; Tarea 3B.1).
- `bind_session_to_tenant` composition with `SessionScope` (nested
  binding works correctly; Tarea 3B.2).
- `TenantId` NewType isinstance limitation (canonical
  normalization via `TenantId(str(...))`; Tarea 3B.1).

## References

- ADR-0007 (event-based enforcement; foundational architecture).
- Decision 3 revised per BLOCKER #30 (callable-only resolver).
- Decision 5-B from Phase 3B kickoff (ContextVar-based binding).
- DR-022 (read enforcement fall-through semantics).
- DR-026 / DR-027 (TBD: middleware-specific decision records,
  Tareas 3B.3-5).
- Phase 2 `TenantContextMiddleware` for cross-adapter reference.
- TenantShield Phase 1 core API (`bind_tenant`, `tenant_scope`,
  `try_current_tenant`, `TenantId`).

---

**End of ADR-0008.**
