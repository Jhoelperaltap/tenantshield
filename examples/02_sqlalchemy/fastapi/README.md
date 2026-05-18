# FastAPI + TenantShield SQLAlchemy adapter (AsyncSession-native)

Demonstrates ASGI middleware integration with `TenantSessionMiddleware`
using SQLAlchemy `AsyncSession` directly -- no `run_in_threadpool` wrap,
no sync `Session()` calls inside `async def` handlers.

This example is the **canonical async-native pattern** for FastAPI +
TenantShield + SQLAlchemy as of Phase 4A (Decision 7-A). It replaces
the Phase 3 sync FastAPI example, which used `run_in_threadpool` to
adapt sync `Session` to `async def` handlers.

## Setup

```bash
uv pip install -e .[dev]
```

(From this directory. The `[dev]` extra installs `pytest` + `httpx`
for running the test suite.)

## Run

```bash
uvicorn app:app --reload
```

Then in another terminal:

```bash
curl -H "X-Tenant-ID: acme" http://localhost:8000/invoices
curl -H "X-Tenant-ID: globex" http://localhost:8000/invoices
```

## Test

```bash
pytest tests/
```

## Key concepts demonstrated

1. **ASGI middleware integration** -- `app.add_middleware(TenantSessionMiddleware, resolve_tenant=...)` binds tenant context per request via Python `contextvars`. Middleware accepts either a synchronous resolver (Phase 3B precedent) or an asynchronous resolver (Sub-fase 4A extension, Decision 3-A).
2. **Dual-mode resolver capability** -- this example showcases both:
   - `app`: synchronous resolver (`resolve_tenant_from_scope`) returning `str | None` directly.
   - `strict_app`: asynchronous resolver (`resolve_tenant_from_scope_async`) returning an awaitable. The middleware detects the coroutine via `inspect.iscoroutine` and awaits transparently.
3. **AsyncSession via FastAPI `Depends`** -- the `get_async_session` dependency yields one `AsyncSession` per request and closes it on completion. Route handlers consume `AsyncSession` directly, no threadpool wrap.
4. **Phase 3A handler reuse** -- TenantShield's Phase 3A event handlers (`@tenant_aware` mapper events + `do_orm_execute` filter) fire transparently under `AsyncSession` because SQLAlchemy routes through `AsyncSession.sync_session_class = Session`. No code changes for adopters: existing `@tenant_aware`-decorated models work identically for sync and async sessions.
5. **Strict mode opt-in** -- `strict_app` instance configured with `on_missing_tenant='raise'` for guaranteed tenant context (DR-026). Requests without `X-Tenant-ID` header raise `MissingTenantContextError`.

## Architecture notes

- Tenant context is bound by `TenantSessionMiddleware.__call__` (async ASGI entry point) after invoking the resolver (sync or async; auto-awaited).
- Internally the middleware uses `SessionScope` (sync context manager) wrapping `await self.app(...)`. The sync `SessionScope` works correctly inside async middleware via Python's `contextvars` per-task propagation (Rule 55, Phase 3B; Tarea 4A.0 Scenario 1 reconfirms for async resolver path).
- `SessionScope` enters tenant scope; exits on response completion (success or exception).
- WebSocket and lifespan scopes pass through without tenant binding (HTTP-only).

## Migration from the Phase 3 sync example

Adopters using the Phase 3 example:

```python
# Phase 3 (deprecated pattern)
@app.get("/invoices/async")
async def get_invoices_async():
    def _query():
        with SessionLocal() as session:
            return session.execute(select(Invoice)).scalars().all()
    rows = await run_in_threadpool(_query)
    ...
```

Should migrate to:

```python
# Phase 4A (canonical async-native pattern)
@app.get("/invoices")
async def get_invoices(session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Invoice))
    rows = result.scalars().all()
    ...
```

No changes needed to `@tenant_aware`-decorated model classes -- Phase 3A
event handlers serve both sync and async sessions identically.

## SQLite in-memory + StaticPool note

This example uses SQLite in-memory (`sqlite+aiosqlite:///:memory:`) with
`StaticPool` + `check_same_thread=False`. This is necessary because the
FastAPI TestClient executes handlers in worker threads, and the default
SQLite in-memory database is per-connection. `StaticPool` shares one
connection across all access, allowing the in-memory database to be
visible to all threads. Real-world adopters using file-backed SQLite,
aiosqlite-file, or PostgreSQL/MySQL (via `asyncpg` / `aiomysql`) do not
need this configuration.

## References

- ADR-0007: event-based enforcement architecture.
- ADR-0008: middleware lifecycle design pattern.
- Decision 3-A (Phase 4 kickoff): parallel async helper surface,
  including dual-mode resolver capability.
- Decision 7-A (Phase 4 kickoff): replace Phase 3 sync FastAPI example
  with this AsyncSession-native version.
- Rule 55: ContextVar across `await` boundaries (validated empirically
  in Tarea 4A.0 Scenarios 1 + 2 for async resolver paths).
