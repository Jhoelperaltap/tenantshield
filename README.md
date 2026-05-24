# TenantShield

**Multi-tenant enforcement engine for Python — prevent cross-tenant data leaks
by construction, not convention.**

## The Problem

Multi-tenant SaaS applications can leak data across tenant boundaries
when a single forgotten `.filter(tenant_id=...)` slips into production.
The leak is silent: queries succeed, responses look normal, and the
breach is often detected only when affected tenants report seeing
data that isn't theirs.

The root cause is structural: tenant scoping is typically enforced by
**convention** (developers remembering to filter), not by the **system**.
One missed filter, one new query path, one ORM method that bypasses
the scoped manager — and the boundary is gone.

## Before TenantShield

```python
# Django: tenant scoping by convention -- one forgotten filter leaks.
class InvoiceView(View):
    def get(self, request):
        # Correct: scoped to current tenant
        invoices = Invoice.objects.filter(tenant_id=request.tenant.id)
        return JsonResponse({"invoices": list(invoices.values())})

    def export_all(self, request):
        # LEAK: no tenant filter -- returns ALL tenants' invoices.
        invoices = Invoice.objects.all()
        return JsonResponse({"invoices": list(invoices.values())})
```

The bug compiles. Tests pass unless they explicitly cover cross-tenant
isolation. Production traffic returns wrong-tenant data. No exception
is raised.

## After TenantShield

```python
# Same model, with TenantShield: scoping is enforced by the system.
from tenantshield.adapters.django import tenant_aware

@tenant_aware
class Invoice(models.Model):
    tenant_id = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # ... rest of model

class InvoiceView(View):
    def get(self, request):
        invoices = Invoice.objects.all()  # auto-scoped to request.tenant
        return JsonResponse({"invoices": list(invoices.values())})

    def export_all(self, request):
        # STILL auto-scoped -- no way to forget.
        invoices = Invoice.objects.all()
        return JsonResponse({"invoices": list(invoices.values())})
```

Outside a tenant context (e.g., a misconfigured background worker), the
same query raises `MissingTenantContextError` instead of silently
returning unscoped data. Cross-tenant writes raise
`CrossTenantAccessError` before the SQL executes.

What was a convention developers had to remember at every call site
becomes a constraint the system enforces by default.

TenantShield is a layer over existing ORMs (Django, SQLAlchemy) and request
frameworks (Django, FastAPI, Flask, any ASGI/WSGI application) that enforces
tenant scoping automatically. The default policy is **deny-by-default**: any
query against a tenant-aware model without an explicit tenant context fails
loudly. Cross-tenant writes are detected and rejected. Tenant context
propagates across `async` boundaries via Python's native `contextvars`.

Adoption is incremental — adapters are activated explicitly and there is no
import-time monkey-patching.

## Status

🟢 **Alpha** — version `0.6.0a0`. The architectural arc from foundation
through production hardening + first cohort-validated maturity is
complete (Phases 0 → 6). Distribution from `v0.6.0-alpha` onward
ships to TestPyPI on every tag (`pip install --index-url
https://test.pypi.org/simple/ tenantshield`); public PyPI distribution
is planned after broader cohort feedback.

## Features

### Framework adapters

- **Django ORM + Django REST Framework**: `tenant_aware` manager + signal
  enforcement + DRF triple defense (permissions + viewset mixin + serializer
  validation) + `TenantContextMiddleware`.
- **SQLAlchemy 2.x sync + async**: `@tenant_aware` declarative decorator +
  event-based write enforcement (`before_insert` / `before_update` /
  `before_delete`) + read filtering via `do_orm_execute` + scope managers
  (`SessionScope` / `AsyncSessionScope`).
- **ASGI middleware**: `TenantSessionMiddleware` (sync ctx mgr with dual-mode
  resolver) + `AsyncTenantSessionMiddleware` (async-native; Phase 5A) for
  FastAPI / Starlette / any ASGI 3.0 framework.
- **WSGI middleware**: `TenantSessionMiddlewareWSGI` with generator-safe
  scope (Flask / Django WSGI / Gunicorn).

### Core capabilities

- **Tenant scope contracts**: `tenant_scope(ctx)` + `atenant_scope(ctx)` for
  explicit binding; `bind_session_to_tenant` / `bind_async_session_to_tenant`
  for SA session binding.
- **Policy engine**: `DenyByDefaultPolicy`, `AllowListPolicy`,
  `RequireScope`, `ChainPolicy`. Composable.
- **Audit bus**: pluggable sinks (`StructLogSink`, `InMemorySink`, `NullSink`,
  or custom). 6 `AuditEventType` values (`CONTEXT_BOUND` /
  `CONTEXT_RELEASED` / `POLICY_ALLOW` / `POLICY_DENY` /
  `ENFORCEMENT_VIOLATION` / `SINK_FAILURE`).
- **Cross-adapter extraction strategies**: `HeaderStrategy`, `HostStrategy`,
  `JWTStrategy`, `CallableStrategy` operating on a minimal `RequestProtocol`
  abstraction. Same strategy instance works across Django + ASGI.

### Production hardening (Phase 5)

- **Structured observability**: `tenantshield.observability` module with a
  9-event taxonomy across scope lifecycle + enforcement + middleware boundaries.
  structlog-based emission with `~6 ns/call` disabled-default gate.
- **Audit-observability dual-pattern**: policy-level audit events + operation-
  level observability events emit at independent gates (sink registry vs
  `is_enabled()` flag). Decision 7-A separation verified empirically.
- **Adopter-extensible processor chain**: OpenTelemetry trace context +
  Prometheus metrics integrate as adopter-prepended structlog processors;
  zero TenantShield-side coupling.

## Install

### Stage 1 — Local wheel distribution

TenantShield is currently distributed via local wheel/sdist artifacts to a
validation cohort. To build and install from the repository:

```bash
uv build
pip install dist/tenantshield-0.5.0a0-py3-none-any.whl
```

Or install a provided wheel artifact directly:

```bash
pip install tenantshield-0.5.0a0-py3-none-any.whl
```

Adapter-specific extras:

```bash
pip install "tenantshield[django]"       # Django + DRF adapter
pip install "tenantshield[sqlalchemy]"   # SQLAlchemy adapter
pip install "tenantshield[jwt]"          # JWT strategy support
pip install "tenantshield[drf]"          # Django REST Framework adapter
```

### Stage 2 — PyPI distribution (upcoming)

Public PyPI distribution is planned after validation cohort feedback.

## Quickstart

The canonical minimum: register an audit sink, define a policy, enter a
tenant scope, and evaluate operations.

```python
from tenantshield import (
    DenyByDefaultPolicy,
    Operation,
    OperationType,
    StructLogSink,
    TenantId,
    bind_tenant,
    evaluate_and_audit,
    register_sink,
    tenant_scope,
)

# 1. Register a sink so audit events go somewhere.
register_sink(StructLogSink())

# 2. Define a policy.
policy = DenyByDefaultPolicy()

# 3. Enter a tenant scope.
ctx = bind_tenant(TenantId("acme"))
with tenant_scope(ctx):
    # 4. Evaluate an operation.
    operation = Operation(
        model="app.Invoice",
        operation_type=OperationType.READ,
        tenant_context=ctx,
    )
    decision = evaluate_and_audit(policy, operation)
    print(decision)  # Allow()
```

Outside a tenant scope, the same evaluation returns
`Deny(reason="No tenant context active for read on 'app.Invoice'")`.

For framework-specific quickstarts (Django, SQLAlchemy + FastAPI,
SQLAlchemy + Flask), see the [Adapters documentation](docs/adapters/index.md)
and the [Examples](#examples) below.

### Enable observability (Phase 5, opt-in)

```python
from tenantshield.observability import configure

configure(emit_events=True)
```

Disabled by default — the gate adds `~6 ns/call` when off and zero log
volume. See [Observability Quick Start](docs/observability/quick-start.md)
for adopter integration patterns.

## Documentation

- **[Getting Started](docs/getting-started.md)** — install + minimal example.
- **[Concepts](docs/concepts/index.md)** — building blocks (TenantContext,
  policies, audit bus, registry).
- **[API Reference](docs/api/index.md)** — complete public surface.
- **[Adapters](docs/adapters/index.md)** — Django + SQLAlchemy + middleware
  integration guides.
- **Observability** ([docs/observability/](docs/observability/)):
  - [Quick Start](docs/observability/quick-start.md) — enable emission +
    configure structlog.
  - [Dual-Pattern](docs/observability/dual-pattern.md) — audit bus +
    observability semantics.
  - [Async Middleware Migration](docs/observability/async-middleware-migration.md)
  - [Production Checklist](docs/observability/production-checklist.md)
  - [OpenTelemetry integration](docs/observability/integration/opentelemetry.md)
  - [Prometheus integration](docs/observability/integration/prometheus.md)
- **[Architectural Decision Records](docs/adr/)** — 12 ADRs documenting
  design decisions.
- **[Changelog](CHANGELOG.md)** — release history with detailed Decision
  Records per phase.

## Examples

Runnable adopter examples lives in [`examples/`](examples/):

- **[FastAPI + SQLAlchemy](examples/02_sqlalchemy/fastapi/)** — async ASGI
  application with `TenantSessionMiddleware`.
- **[Flask + SQLAlchemy](examples/02_sqlalchemy/flask/)** — sync WSGI
  application with `TenantSessionMiddlewareWSGI`.
- **[CLI + SQLAlchemy](examples/02_sqlalchemy/cli/)** — framework-agnostic
  background-worker pattern with `SessionScope`.
- **[Django adopter starter](examples/01_django/)** — Django project
  template wired with TenantShield middleware + admin.

## Compatibility

| | Versions |
|---|---|
| Python | 3.11, 3.12, 3.13 |
| Django | 4.2 LTS, 5.x |
| SQLAlchemy | 2.x (sync + async) |
| FastAPI | `>=0.115` |
| Flask | recent versions (WSGI standard) |

`structlog>=25.0,<26.0` is the only required runtime dependency.

## Architectural maturity

- **Phases shipped**: 0 (foundation) → 1 (core API) → 2 (Django + DRF) →
  3 (SQLAlchemy sync) → 4 (SQLAlchemy async + cross-adapter strategies) →
  5 (production hardening).
- **557 tests** (541 library + 16 example) with **99.63% library coverage**.
- **12 ADRs** + **43 active Decision Records** + **73 normative Rules**.
- **0 architectural BLOCKERs** in Phase 5 (best Phase profile sustained from
  Phase 4).

See the [Documentation](https://jhoelperaltap.github.io/tenantshield/) for
comprehensive guides, API reference, and architectural decisions.

## License

Released under the [Apache License 2.0](LICENSE).
