# Adapters

TenantShield's core (Phase 1) provides the enforcement engine: identity,
context, exceptions, policies, audit bus, and model registry. **Framework
adapters arrive in subsequent phases**:

- **Phase 2** — Django + Django REST Framework
- **Phase 3** — SQLAlchemy
- **Phase 4** — Celery + asyncio propagation utilities

Each adapter integrates TenantShield with its target framework's
idioms: query filtering, signal handling, middleware, task headers.

If you need TenantShield today and your framework is not yet supported,
you can wire the core manually. See [Concepts](../concepts/index.md) and
[API Reference](../api/index.md).
