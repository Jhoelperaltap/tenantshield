# FastAPI + TenantShield SQLAlchemy adapter

Demonstrates ASGI middleware integration via `TenantSessionMiddleware`.

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
curl -H "X-Tenant-ID: acme" http://localhost:8000/invoices/sync
curl -H "X-Tenant-ID: globex" http://localhost:8000/invoices/sync
curl -H "X-Tenant-ID: acme" http://localhost:8000/invoices/async
```

## Test

```bash
pytest tests/
```

## Key concepts demonstrated

1. **ASGI middleware integration** -- `app.add_middleware(TenantSessionMiddleware, resolve_tenant=...)` binds tenant context per request via Python `contextvars`.
2. **Callable resolver pattern** -- extracts `X-Tenant-ID` header from ASGI scope. Phase 2B strategies are **NOT** used (Django-bound per BLOCKER #30 resolution; see Sub-fase 3B kickoff Decision 3 revised).
3. **Sync vs async route handlers** -- TenantShield's SQLAlchemy adapter is sync-only in Phase 3 (`AsyncSession` deferred to Phase 4). Two correct patterns:
   - **`/invoices/sync`**: `def` handler, calls SA `Session()` directly. **Recommended** for FastAPI + SA combination.
   - **`/invoices/async`**: `async def` handler with `starlette.concurrency.run_in_threadpool` wrapping SA operations.
   - **NEVER** call sync `Session()` directly inside `async def` without threadpool -- this blocks the event loop.
4. **ContextVar propagation across `await`** -- per Rule 55 (Phase 3B), tenant scope set sync by middleware is visible across `await` boundaries within the same task via asyncio per-task `copy_context()` semantics.
5. **Strict mode opt-in** -- `strict_app` instance configured with `on_missing_tenant='raise'` for guaranteed tenant context (DR-026). Requests without `X-Tenant-ID` header raise `MissingTenantContextError`.

## Architecture notes

- Tenant context is bound by `TenantSessionMiddleware.__call__` (async ASGI entry point).
- Internally the middleware uses `SessionScope` (sync context manager) wrapping `await self.app(...)`.
- `SessionScope` enters tenant scope; exits on response completion (success or exception).
- WebSocket and lifespan scopes pass through without tenant binding (HTTP-only).

## SQLite in-memory + threadpool note

This example uses SQLite in-memory (`sqlite:///:memory:`) with `StaticPool` + `check_same_thread=False`. This is necessary because the FastAPI TestClient and `run_in_threadpool` execute handlers in worker threads, and the default SQLite in-memory database is per-connection. `StaticPool` shares one connection across all access, allowing the in-memory database to be visible to all threads. Real-world adopters using file-backed SQLite or other databases (PostgreSQL, MySQL) do not need this configuration.
