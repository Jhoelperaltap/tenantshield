# Getting Started

## Installation

```bash
pip install tenantshield
```

Or with `uv`:

```bash
uv add tenantshield
```

## A minimal example

```python
from tenantshield import (
    DenyByDefaultPolicy,
    Operation,
    OperationType,
    TenantId,
    bind_tenant,
    evaluate_and_audit,
    register_sink,
    StructLogSink,
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

Outside a tenant scope, the same evaluation would return
`Deny(reason="No tenant context active for read on 'app.Invoice'")`.

## Next steps

- [Concepts](concepts/index.md) — understand the building blocks.
- [API Reference](api/index.md) — the complete API.
