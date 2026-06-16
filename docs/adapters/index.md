# Adapters

TenantShield's core (Phase 1) provides the enforcement engine: identity,
context, exceptions, policies, audit bus, and model registry. Framework
adapters bind that core to a specific ORM or framework's idioms (query
filtering, signal handling, middleware, task headers).

This page summarizes the **current adapter status honestly** — what is
production-validated, what is functional but still maturing, and what is
on the roadmap but not yet shipped.

## Status matrix

| Adapter | Status | Notes |
|---|---|---|
| **Django ORM** | ✅ **Validated in production** | Reference adopter (Counterbook) integrated TenantShield over 6 consecutive sprint cycles (~196 commits, 0 architectural findings introduced). SOC2 audit posture validated (SC-13 + AT-REST + CC6.1 MET). |
| **SQLAlchemy 2.x sync + async** | 🔵 **Functional, Phase 7 gaps documented** | Read/write enforcement operational via SA events. Missing parity items tracked: see [Known limitations (Phase 7)](#known-limitations-sqlalchemy-phase-7) below. |
| **Django REST Framework** | 🔵 **Functional, test coverage expanding** | Triple defense pattern (permissions + viewset mixin + serializer validation) operational. Integration test surface broadening as more DRF idioms are exercised. |
| **ASGI / WSGI middleware** | ✅ **Production-shipped** | `TenantSessionMiddleware`, `AsyncTenantSessionMiddleware`, and `TenantSessionMiddlewareWSGI` shipped in Phases 4-5. |
| **Cross-adapter strategies** | ✅ **Production-shipped** | `HeaderStrategy`, `HostStrategy`, `JWTStrategy`, `CallableStrategy` — single API across all adapters. |

## Where to learn more

- [Concepts](../concepts/index.md) — core principles applied to all adapters
  (security posture, governance model, deny-by-default semantics).
- [Cross-adapter parity matrix](../concepts/cross-adapter-parity.md) — feature-by-feature comparison Django ↔ SQLAlchemy.
- [API Reference](../api/index.md) — complete public surface of each adapter.
- The [`getting-started.md`](../getting-started.md) page includes per-framework quickstarts (Django, SQLAlchemy + FastAPI, SQLAlchemy + Flask).

## Known limitations (SQLAlchemy, Phase 7)

The SQLAlchemy adapter has two architectural gaps relative to the Django
adapter, both tracked for Phase 7:

- **`_unsafe_unscoped` parity** (Phase 7 Item 31) — Django's
  `@tenant_aware` decorator exposes `Model._unsafe_unscoped` for explicit,
  audited bypass with `ENFORCEMENT_BYPASS` event emission. The SA adapter
  does not yet provide this surface; bulk operations that need to cross
  tenant boundaries currently require manual session unbinding.

- **`auto_propagate_from_parent_fk` parity** (Phase 7 Item 32) — Django's
  `@tenant_aware(auto_propagate_from_parent_fk="parent")` automatically
  fills `tenant_id` from a parent FK on insert. The SA adapter does not
  yet provide this propagation; child models must set `tenant_id` explicitly.

Both items are catalogued in [`docs/concepts/cross-adapter-parity.md`](../concepts/cross-adapter-parity.md)
with empirical context. The SA adapter is **architecturally stronger**
than the pre-Phase-6 Django adapter on one axis — `before_*` event
listeners fire pre-SQL and raise rather than returning silent zero rows
— so the gaps are scoped to specific Django features, not foundational
correctness.

## Roadmap / Planned

The following adapters are **not yet shipped** and should not be relied
on for current usage:

- **Celery integration** — propagation of tenant context across `apply_async`
  task boundaries (headers serialization + worker-side rebinding). On the
  Phase 7+ roadmap; no implementation in `src/tenantshield/adapters/` yet.
  If you need TenantShield with Celery today, you can manually bind/release
  tenant context inside task bodies using the public `tenant_scope(ctx)` /
  `bind_tenant(...)` core APIs.

- **FastAPI native dependency** — currently FastAPI is supported via the
  generic ASGI middleware (`AsyncTenantSessionMiddleware`). A native
  FastAPI dependency (`Depends(...)`) is on the backlog as a DX
  improvement, not a correctness gap.

If your framework is not listed here and you need TenantShield support,
the core API (`tenant_scope`, `bind_tenant`, `TenantId`, audit bus,
strategies) is framework-agnostic — see [Concepts](../concepts/index.md)
and [API Reference](../api/index.md) for the integration surface.
