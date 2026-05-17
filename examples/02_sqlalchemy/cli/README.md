# CLI + TenantShield SQLAlchemy adapter

Demonstrates **framework-agnostic** TenantShield usage via `SessionScope`
and `bind_session_to_tenant` for non-web applications: batch jobs, ETL
pipelines, admin scripts, data migrations, scheduled reports.

No web framework. No middleware. Pure SQLAlchemy + TenantShield core.

## Setup

```bash
uv pip install -e .[dev]
```

(From this directory. The `[dev]` extra installs `pytest`.)

## Run

```bash
# Single tenant report
python cli.py report --tenant acme

# Multi-tenant sweep (all known tenants)
python cli.py sweep

# Nested binding demo
python cli.py nested

# Seed demo data (in-memory; per-invocation reset)
python cli.py seed
```

## Test

```bash
pytest tests/
```

## Key concepts demonstrated

1. **`SessionScope` direct usage** -- context manager establishes tenant scope without HTTP middleware. Pattern: `with SessionScope(tenant=...): session.query(...)`.
2. **`bind_session_to_tenant` explicit binding** -- alternate helper for explicit tenant binding (typically inside loops or nested scopes).
3. **Composition** -- `SessionScope` + `bind_session_to_tenant` compose: nested binding overrides outer; outer restored on inner exit (per Sub-fase 3B Tarea 3B.2 empirical pattern).
4. **Batch sweep pattern** -- iterate tenants, rebind scope per tenant, perform batch operations. Canonical adopter pattern for nightly reports or ETL pipelines.

## When to use this pattern

- Batch jobs that process multiple tenants sequentially.
- ETL pipelines extracting/transforming/loading per-tenant.
- Admin scripts performing tenant-isolated maintenance.
- Data migrations operating on tenant-scoped data.
- Scheduled reports generated per tenant.
- Test fixtures setting up tenant-scoped data.

## Why not middleware?

Middleware exists for **request-response patterns** (HTTP). CLI scripts have no request; they have a control flow defined by the script itself. `SessionScope` lets the script explicitly bind tenant context to arbitrary code blocks without HTTP middleware overhead.

The same TenantShield enforcement guarantees apply: cross-tenant access raises `CrossTenantAccessError`; flush-time enforcement applies per DR-021 / DR-025.

## In-memory database note

This example uses SQLite in-memory (`sqlite:///:memory:`) with `StaticPool` for simplicity. The in-memory database is reset on each `python cli.py ...` invocation; `cli.py` auto-seeds data before any non-seed command runs. Real adopters use a persistent database (file-backed SQLite, PostgreSQL, MySQL, etc.).
