# Flask + TenantShield SQLAlchemy adapter

Demonstrates WSGI middleware integration via `TenantSessionMiddlewareWSGI`.

## Setup

```bash
uv pip install -e .[dev]
```

(From this directory. The `[dev]` extra installs `pytest` for the
test suite.)

## Run

```bash
flask --app app run
```

Then in another terminal:

```bash
curl -H "X-Tenant-ID: acme" http://localhost:5000/invoices
curl -H "X-Tenant-ID: globex" http://localhost:5000/invoices
```

## Test

```bash
pytest tests/
```

## Key concepts demonstrated

1. **WSGI middleware integration** -- `app.wsgi_app = TenantSessionMiddlewareWSGI(app.wsgi_app, resolve_tenant=...)` wraps Flask's WSGI handler with tenant context binding.
2. **Callable resolver pattern** -- extracts `X-Tenant-ID` header from WSGI `environ` dict (key: `HTTP_X_TENANT_ID`). Phase 2B `HeaderStrategy` **NOT** used (Django-bound per BLOCKER #30 resolution; see Sub-fase 3B kickoff Decision 3 revised).
3. **WSGI generator pattern (Rule 54)** -- `TenantSessionMiddlewareWSGI` internally uses `yield from self.app(...)` keeping tenant scope active during full response body iteration. Critical for streaming responses where the inner app generates chunks lazily.
4. **Strict mode opt-in (DR-026)** -- `strict_app` factory configures middleware with `on_missing_tenant='raise'`. Requests without `X-Tenant-ID` header raise `MissingTenantContextError`.

## Architecture notes

- Tenant context bound by `TenantSessionMiddlewareWSGI.__call__` (sync WSGI entry point).
- Internally uses `SessionScope` wrapping `yield from self.app(...)`.
- Scope active during full response iteration (streaming-safe per Rule 54).
- Generator pattern preserves scope across body chunks generated lazily.

## SQLite in-memory + threaded test client note

This example uses SQLite in-memory (`sqlite:///:memory:`) with `StaticPool` + `check_same_thread=False`. Flask's test client may execute handlers in worker threads, and the default SQLite in-memory database is per-connection. `StaticPool` shares one connection across all access, allowing the in-memory database to be visible to all threads. Real-world adopters using file-backed SQLite or PostgreSQL/MySQL do not need this configuration.

## Why not Phase 2B strategies?

TenantShield's Phase 2B `TenantExtractionStrategy` classes (`HeaderStrategy`, `JWTStrategy`, `SubdomainStrategy`) are Django-bound -- they use `request.META` and `request.get_host()`. Flask/Werkzeug `Request` objects have different shapes.

Sub-fase 3B BLOCKER #30 resolved: SA middleware accepts callable resolvers only. Adopters write framework-specific callable resolvers (typically 1-3 LOC for header extraction).

Cross-adapter strategy unification deferred per BLOCKER #30 Path (c) resolution.
