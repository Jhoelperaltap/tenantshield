# Async Middleware Migration Guide

TenantShield offers three middleware classes for binding tenant context
per request. All emit the same observability events; adopters choose
based on framework and execution model.

| Middleware | Internal context manager | Framework |
|---|---|---|
| `TenantSessionMiddleware` | `with SessionScope(...)` | ASGI (sync ctx mgr) |
| `AsyncTenantSessionMiddleware` | `async with AsyncSessionScope(...)` | ASGI (async ctx mgr) |
| `TenantSessionMiddlewareWSGI` | `with SessionScope(...)` + `yield from` | WSGI |

## Phase 4A dual-mode resolver

`TenantSessionMiddleware` (Phase 3B + 4A) accepts either a synchronous
resolver or an async resolver returning an `Awaitable`. The middleware
detects the return type via `inspect.iscoroutine` and awaits when needed.
Existing synchronous resolvers continue to work unchanged.

```python
# Synchronous resolver -- Phase 3B precedent
def resolve_tenant(scope):
    for name, value in scope.get("headers", []):
        if name == b"x-tenant-id":
            return value.decode("latin-1")
    return None

# Asynchronous resolver -- Phase 4A extension
async def resolve_tenant_async(scope):
    async with db_pool.connection() as conn:
        return await conn.fetchval(
            "SELECT tenant FROM sessions WHERE token = $1",
            extract_token(scope),
        )
```

Either resolver works with `TenantSessionMiddleware`. Decision 3-C
ratified that this dual-mode coexistence is permanent.

## When to use `AsyncTenantSessionMiddleware`

Sub-fase 5A introduced `AsyncTenantSessionMiddleware` as the
ASGI-native variant. It wraps the inner app with
`async with AsyncSessionScope(...)` -- behavioral parity at the
ContextVar layer, architectural clarity at the middleware surface.

Choose `AsyncTenantSessionMiddleware` when:

- The deployment is async-native and you want explicit async semantics.
- You prefer the async context manager signal in code review.
- The application uses `AsyncSession` exclusively (no sync `Session`).

Choose `TenantSessionMiddleware` when:

- You have an existing Phase 3B / 4A deployment that works today.
- The application mixes `Session` and `AsyncSession`.
- The dual-mode resolver pattern fits your stack.

Both middleware variants emit the same observability events:

- `tenant.middleware.request_bound` -- before the scope ctx mgr enters.
- `tenant.middleware.request_unbound` -- after the scope ctx mgr exits.

The only difference adopters observe is the `middleware_class` field
(`"TenantSessionMiddleware"` vs `"AsyncTenantSessionMiddleware"` vs
`"TenantSessionMiddlewareWSGI"`).

## Migration steps

1. Register the new middleware alongside (or in place of) the old one.
2. Run integration tests; confirm `tenant.middleware.*` events still emit.
3. Verify `tenant.scope.*` events nest correctly between bound and unbound:
   `request_bound` -> `scope.entered` -> ... -> `scope.exited` -> `request_unbound`.
4. Adjust dashboards / log filters to include the new `middleware_class`
   value.

## See also

- [Quick Start](quick-start.md).
- [Dual-Pattern](dual-pattern.md).
