# TenantShield

A multi-tenant enforcement engine for Python that eliminates cross-tenant
data leaks **by construction**.

## Status

Pre-1.0 alpha. Phase 1 (core) is complete; framework adapters (Django,
SQLAlchemy, Celery, DRF) arrive in subsequent phases.

## Quick links

- [Getting Started](getting-started.md) — install and run your first example.
- [Concepts](concepts/index.md) — what each part of TenantShield does.
- [API Reference](api/index.md) — full API documentation.
- [ADRs](adr/0001-commit-signing-deferral.md) — architectural decisions.

## Why TenantShield?

Multi-tenant data leaks are common. Most defenses are reactive (audits,
manual review, hope). TenantShield is preventive: it makes leaks fail
**loudly** instead of silently corrupt data.

If `bind_tenant(...)` was never called and a tenant-aware query runs,
TenantShield raises an exception. There is no implicit fallback.
