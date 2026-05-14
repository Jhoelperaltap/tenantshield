# TenantShield

Multi-tenant enforcement engine for Python — prevent cross-tenant data leaks by construction, not convention.

<!-- ci, coverage, pypi, python versions, license — to be populated when GitHub repo is created -->

## Status

🚧 Pre-alpha — under active development. Do not use in production.

## What is TenantShield?

In multi-tenant SaaS applications, every query, mutation, and join must be scoped to the current tenant. The common pattern — adding `.filter(tenant_id=request.tenant)` by hand on every call site — relies on developer discipline to never forget. One missed filter on one code path leaks data across tenants, and the bug is often invisible until an audit, a customer report, or a breach.

TenantShield is a layer on top of existing ORMs (Django, SQLAlchemy) and task systems (Celery, DRF) that enforces tenant scoping automatically. The default policy is deny-by-default: any query against a tenant-aware model without an explicit tenant context fails loudly. Cross-tenant joins are detected and rejected. Tenant context propagates across async boundaries and worker queues. Adoption is incremental — adapters are activated explicitly and there is no import-time monkey-patching.

## Install

```sh
pip install tenantshield
```

> Not yet on PyPI. Install will be available starting with `v0.0.1-alpha.0`.

## Quickstart

> Coming in Phase 1. See [Roadmap](./TENANTSHIELD_ROADMAP.md) for the current development plan.

## Roadmap

Phase-by-phase development plan, deliverables, and acceptance criteria are defined in [TENANTSHIELD_ROADMAP.md](./TENANTSHIELD_ROADMAP.md).

## License

Released under the [Apache License 2.0](./LICENSE).
