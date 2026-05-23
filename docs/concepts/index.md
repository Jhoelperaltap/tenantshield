# Concepts

TenantShield is built around five concepts. Each is documented in detail
in the [API Reference](../api/index.md); this page gives a brief overview.

## TenantContext

The active tenant for the current execution flow. Stored in a
`ContextVar`, so it works seamlessly across sync and async code without
manual threading.

`bind_tenant(tenant_id)` creates a context. `tenant_scope(ctx)` activates
it for the duration of a `with` block. Inside the scope, `current_tenant()`
returns the active context; outside, it raises `MissingTenantContextError`.

## Exceptions

A typed hierarchy rooted at `TenantShieldError`. The most important
subclasses are `MissingTenantContextError` (no tenant active when one was
required) and `CrossTenantAccessError` (an operation tried to touch another
tenant's data). All carry structured fields and serialize via `to_dict()`.

## Policies

A `Policy` decides whether an `Operation` is allowed. Decisions are one of
`Allow`, `Deny(reason)`, or `RequireScope(filter_spec)`. Built-in policies
include `DenyByDefaultPolicy`, `AllowListPolicy`, and `ChainPolicy` for
composition.

## Audit bus

Every significant event (context entered, context released, policy
evaluated, sink failed) is emitted to a registered set of sinks. Sinks are
duck-typed; provide your own or use the built-in `NullSink`, `InMemorySink`,
or `StructLogSink`. Sinks that raise do not break the bus.

## ModelRegistry

Tracks which model classes are tenant-aware and which attribute carries
the tenant id. Used by adapters (Phase 2+) to know what to filter and what
to leave alone. Register models with `@register_model` or
`register_model(Cls)`.

## Further reading

- **[Security posture](security-posture.md)** -- the triple-layer defense
  model (manager scope + audit + HARD REJECT) empirically validated
  across three Counterbook adoption cycles (Phase 6).
- **[Adopter governance pattern](adopter-governance.md)** -- recommended
  adopter ADR-driven governance layer per TenantShield API surface.
- **Architectural Decision Records** -- 13 ADRs documenting the
  contracts adopters depend on. See the ADR section in the site
  navigation.
