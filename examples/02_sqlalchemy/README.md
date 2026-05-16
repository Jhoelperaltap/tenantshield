# TenantShield SQLAlchemy adapter examples

Runnable demonstrations of the SQLAlchemy adapter shipped in Phase 3
(Sub-fase 3A + 3B). Each example is self-contained with its own
`pyproject.toml` and can be installed and exercised independently.

## Examples

- **`fastapi/`** -- ASGI integration via `TenantSessionMiddleware`
  (FastAPI). Demonstrates sync vs async route patterns and strict
  mode enforcement (`on_missing_tenant='raise'`).
- **`flask/`** -- WSGI integration via `TenantSessionMiddlewareWSGI`
  (Flask). Demonstrates streaming-safe generator pattern.
- **`cli/`** -- Framework-agnostic core via `SessionScope` +
  `bind_session_to_tenant`. Demonstrates non-web tenant binding
  contexts.

All examples share a common SQLAlchemy `Invoice` model schema with
the `tenant_id` column.

## Important: SQLAlchemy is sync-only in Phase 3

TenantShield's SQLAlchemy adapter (Phase 3) supports the sync
`Session` API only. `AsyncSession` support is deferred to Phase 4
(see ADR-0008 architectural notes).

**For FastAPI users:** use `def` route handlers (sync) OR `async def`
route handlers with `starlette.concurrency.run_in_threadpool` for SA
operations. **NEVER** call sync `Session()` directly inside `async def`
without threadpool -- this blocks the event loop. See
`fastapi/app.py` for both patterns documented.

## Tenant resolution: callable resolvers only

Per BLOCKER #30 resolution (Sub-fase 3B Tarea 3B.0), TenantShield's
SQLAlchemy middleware accepts callable resolvers only. The Phase 2B
`TenantExtractionStrategy` classes (e.g., `HeaderStrategy`,
`JWTStrategy`) are Django-bound (they use `request.META` and
`request.get_host()`) and are **NOT** reusable in SQLAlchemy
middleware.

Each example shows the canonical callable resolver pattern for its
framework: a function that accepts the framework's request/scope/
environ shape and returns a `TenantId`/`str`/`None`.

## See also

- `docs/adr/0006-sqlalchemy-2-0-only.md` -- adapter scope rationale.
- `docs/adr/0007-event-based-enforcement.md` -- enforcement
  architecture (mapper + session events).
- `docs/adr/0008-middleware-lifecycle-design.md` -- middleware
  lifecycle (two-layer architecture; ContextVar-based binding).
