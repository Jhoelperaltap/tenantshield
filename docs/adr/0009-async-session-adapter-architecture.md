# ADR-0009 -- AsyncSession adapter architecture for Phase 4A

**Status:** Accepted.
**Date:** 2026-05-17.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.
**Related:** Decision 3-A (parallel async lifecycle helpers),
Decision 7-A (FastAPI sync example replacement), ADR-0008 (Phase 3B
middleware lifecycle, sync precedent), DR-028 through DR-032
(Sub-fase 4A specific decisions), Rule 55 (sync ContextVar across
async semantics, Phase 3B origin), Rule 56 (StaticPool threaded test
client, generalized in Sub-fase 4A).

## Context

Phase 3 delivered the synchronous SQLAlchemy adapter (Session-based)
end-to-end: `@tenant_aware` decorator, mapper event-based write
enforcement, `do_orm_execute` read filtering, `SessionScope` +
`bind_session_to_tenant` lifecycle helpers, and ASGI/WSGI
`TenantSessionMiddleware`. Phase 4A extends to `AsyncSession`-native
operation for ASGI applications, FastAPI deployments, and async-first
SQLAlchemy 2.0+ adopters, closing Decision 2-A's deferral from Sub-fase
3B.

Three architectural questions emerged at Sub-fase 4A kickoff:

1. Should TenantShield introduce a new event-handler layer for
   `AsyncSession` or reuse Phase 3A handlers?
2. How should the async API surface relate to the existing sync helpers
   (`SessionScope`, `bind_session_to_tenant`)?
3. How should `TenantSessionMiddleware` accept tenant resolvers when
   tenant lookup is naturally asynchronous (DB / external API)?

## Decision

Phase 4A introduces a parallel async surface layered over the existing
Phase 3A event handlers, leveraging SQLAlchemy's
`AsyncSession.sync_session_class` attribute for transparent handler
reuse. The architectural pillars:

### 1. Phase 3A handler reuse via `sync_session_class`

SQLAlchemy `AsyncSession` operations route through
`AsyncSession.sync_session_class` (= sync `Session`). The Phase 3A
event registration `event.listen(Session, "do_orm_execute", ...)` plus
mapper-level `event.listen(cls, "before_insert", ...)` dispatch for
both sync and async flush paths.

Empirically validated in Tarea 4A.0 Scenarios 3 and 4, then re-verified
end-to-end in Tareas 4A.3 (write enforcement under
`await session.flush()`) and 4A.4 (read enforcement under
`await session.execute(select(...))`). Zero new event handlers were
introduced in Sub-fase 4A.

### 2. Parallel async lifecycle helpers (Decision 3-A)

New public API symbols added at the adapter level:

- `tenantshield.adapters.sqlalchemy.AsyncSessionScope` -- async context
  manager mirroring `SessionScope` parameter parity (`tenant`,
  `resolve_tenant`) and fall-through / mutual-exclusivity semantics.
- `tenantshield.adapters.sqlalchemy.bind_async_session_to_tenant` --
  async context manager mirroring `bind_session_to_tenant` parameter
  parity (single positional `tenant`, raise on `None` / empty).

Both implemented as `@asynccontextmanager`-decorated functions (matching
Phase 3B `@contextmanager` precedent for sync counterparts) and wrap
`tenantshield.atenant_scope` internally. Adopter mental model: pick the
sync or async helper based on Session flavor, not dual-mode magic.

### 3. Dual-mode resolver in `TenantSessionMiddleware` (ASGI only)

`TenantSessionMiddleware` accepts resolvers that are either synchronous
(Phase 3B precedent, returning `TenantId | str | None`) or asynchronous
(Sub-fase 4A extension, returning
`Awaitable[TenantId | str | None]`). The middleware invokes the
resolver, inspects the return via `inspect.iscoroutine`, and awaits
when needed. Backward compatibility preserved: existing synchronous
resolvers continue working unchanged with no signature widening
(`ASGIResolveTenant = Callable[[ASGIScope], Any]` already accepts
awaitable returns).

`TenantSessionMiddlewareWSGI` remains sync-only by design; WSGI is
inherently synchronous.

### 4. Sync/async coexistence via shared ContextVar

The same `_tenant` `ContextVar` underlies both sync `tenant_scope` and
async `atenant_scope`. Tenant binding set in one flavor is visible to
the other within the same task. `asyncio.to_thread` propagates the
context to worker threads, so sync utilities called from async code
observe the active tenant; conversely, sync code that sets a scope and
invokes an async callable via `asyncio.run` propagates context to the
callee.

Empirically validated in Tarea 4A.0 Scenarios 1 (intra-task await
propagation), 2 (cross-task `asyncio.gather` isolation), and 7
(`asyncio.to_thread` propagation), then formalized as integration
tests in Tarea 4A.7.

## Alternatives considered

### Alternative A -- New async-specific event handlers

Define a parallel `_async_before_insert_handler`, etc., registered via
`event.listen(AsyncSession, ...)` directly.

**Rejected because:**

- SQLAlchemy 2.0+ does not dispatch mapper events on `AsyncSession`
  directly; events fire at the underlying sync engine flush layer.
  Registering on `AsyncSession` would not fire.
- `AsyncSession.sync_session_class = Session` already provides correct
  dispatch via Phase 3A handlers, empirically verified.
- Parallel handlers would risk dispatch divergence over time as
  SQLAlchemy evolves; single source of truth preferred.

### Alternative B -- `SessionScope` made dual-mode (async-aware)

Detect whether `SessionScope` is being used from async context (e.g.,
via `asyncio.get_event_loop()`) and dispatch accordingly to sync or
async tenant binding.

**Rejected because:**

- Adopter mental model becomes unclear ("does `SessionScope` work
  async? when?"). Decision 3-A explicitly chose parallel helpers over
  dual-mode magic.
- Detection logic is error-prone (event loops, nested asyncio.run,
  etc.).
- Sync `tenant_scope` already works correctly inside async code via
  ContextVar; the issue is purely API ergonomics. A dedicated
  `AsyncSessionScope` documents intent clearly.

### Alternative C -- Single async resolver-only middleware extension

Replace synchronous resolver support in `TenantSessionMiddleware`,
forcing all adopters to migrate to async resolvers.

**Rejected because:**

- Breaks backward compatibility with Phase 3B sync resolvers.
- Alpha-stage TenantShield prefers compatibility-preserving extensions
  per project governance.
- `Callable[..., Any]` type alias already permits dual-mode at the
  type-system level; only runtime dispatch needed via
  `inspect.iscoroutine`. Two-line extension preserves all existing
  patterns.

## Consequences

### Positive

- **Phase 3A design choice pays compound dividends:** the event-based
  enforcement architecture (chosen in ADR-0007) anticipates async
  extension without explicit foresight. Sub-fase 4A integration cost
  dramatically reduced (zero new event handlers).
- **Backward compatibility preserved:** existing sync adopters using
  `SessionScope` / `bind_session_to_tenant` / sync resolvers continue
  to work unchanged. No migration required for existing code.
- **Adopter mental model coherent:** parallel sync / async API surface
  mirrors SQLAlchemy 2.0's own `Session` / `AsyncSession` separation.
  Adopters pick the helper matching their Session flavor.
- **Mixed sync/async architectures supported:** ContextVar binding
  shared across flavors; `asyncio.to_thread` propagation enables real
  adopter patterns (async route + sync background task; sync utility
  + async wrapper).
- **No public API breakage:** signature widening for
  `TenantSessionMiddleware.resolve_tenant` is permissive (existing
  callers' types remain valid).

### Negative

- **Async resolver runtime overhead:** every ASGI request incurs one
  `inspect.iscoroutine()` check post-resolver-invocation. Benchmarked
  negligible (microseconds; single isinstance check), documented as
  intentional design trade-off for adopter ergonomics.
- **WSGI variant remains sync-only:** adopters needing async tenant
  resolution from a WSGI context must either pre-resolve before the
  request reaches the middleware or migrate to ASGI. Acceptable
  per Decision 3-A (parallel surface, not dual-mode magic).
- **Two helper functions instead of one:** `SessionScope` and
  `AsyncSessionScope` are separately documented and tested. Adopter
  documentation surface grows; mitigated by exact parameter parity
  and shared examples.

### Cross-flavor pattern alignment

| Aspect | Sync (Phase 3) | Async (Phase 4A) |
|---|---|---|
| Lifecycle helper | `SessionScope` | `AsyncSessionScope` |
| Direct binding | `bind_session_to_tenant` | `bind_async_session_to_tenant` |
| Internal scope primitive | `tenant_scope` | `atenant_scope` |
| Event handler dispatch | `event.listen(Session, ...)` | `event.listen(Session, ...)` (reused via `sync_session_class`) |
| Middleware (HTTP request) | `TenantSessionMiddleware` (sync resolver) | `TenantSessionMiddleware` (sync OR async resolver, dual-mode) |
| Middleware (WSGI) | `TenantSessionMiddlewareWSGI` | n/a (WSGI is sync-only) |
| Example | Flask (`examples/02_sqlalchemy/flask/`), CLI (`examples/02_sqlalchemy/cli/`) | FastAPI AsyncSession (`examples/02_sqlalchemy/fastapi/`, replaces Phase 3 sync version per Decision 7-A) |

## Empirical evidence

Sub-fase 4A Tareas 4A.0-4A.7 empirically validated:

- ContextVar visibility across `await` boundaries within the same
  task (Tarea 4A.0 Scenario 1; reconfirms Rule 55).
- ContextVar isolation across `asyncio.gather` concurrent tasks
  (Tarea 4A.0 Scenario 2).
- `do_orm_execute` fires under `await AsyncSession.execute(select(...))`
  (Tarea 4A.0 Scenario 3; Tarea 4A.4 end-to-end).
- Mapper events fire under `await session.flush()` (Tarea 4A.0
  Scenario 4; Tarea 4A.3 end-to-end).
- `async_sessionmaker` vs `sessionmaker(class_=AsyncSession)` are
  functionally equivalent for adopter use; `async_sessionmaker`
  canonical (Tarea 4A.0 Scenario 5).
- `async with` nesting composes cleanly (Tarea 4A.0 Scenario 6;
  Tarea 4A.1).
- `asyncio.to_thread` propagates ContextVar (Tarea 4A.0 Scenario 7;
  Tarea 4A.7 formalized).
- AsyncSession + sync Session coexistence in same process with shared
  tenant binding (Tarea 4A.7).
- ASGI middleware async resolver dual-mode dispatch (Tarea 4A.5;
  5 tests including backward compatibility).

## References

- ADR-0006 (SA 2.0+ only) -- baseline version requirement.
- ADR-0007 (event-based enforcement) -- architectural foundation; this
  ADR extends ADR-0007's design choice to async with zero modifications
  to the handler layer.
- ADR-0008 (Phase 3B middleware lifecycle) -- sync precedent; Sub-fase
  4A extends middleware resolver semantics without altering the core
  lifecycle architecture.
- Decision 3-A, 7-A (Phase 4 kickoff ratifications).
- DRs 028-032 (Sub-fase 4A specific decision records).
- Rule 55 (ContextVar across async), Rule 56 (StaticPool threaded test
  client; generalized in Sub-fase 4A coexistence tests).

---

**End of ADR-0009.**
