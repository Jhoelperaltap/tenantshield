# Getting Started

## Installation

The supported install paths during the alpha series:

### From the GitHub tag (recommended for adopters)

```bash
pip install git+https://github.com/Jhoelperaltap/tenantshield.git@v0.5.4-alpha
```

### From the source tree (editable install for cohort dogfood)

```bash
git clone https://github.com/Jhoelperaltap/tenantshield
cd tenantshield
pip install -e .
```

Or with `uv`:

```bash
uv add "git+https://github.com/Jhoelperaltap/tenantshield.git@v0.5.4-alpha"
```

### Adapter extras

Install only the adapters you use:

```bash
pip install "tenantshield[django] @ git+https://github.com/Jhoelperaltap/tenantshield.git@v0.5.4-alpha"
pip install "tenantshield[sqlalchemy] @ git+https://github.com/Jhoelperaltap/tenantshield.git@v0.5.4-alpha"
pip install "tenantshield[drf] @ git+https://github.com/Jhoelperaltap/tenantshield.git@v0.5.4-alpha"
pip install "tenantshield[jwt] @ git+https://github.com/Jhoelperaltap/tenantshield.git@v0.5.4-alpha"
```

## Troubleshooting installation

### `uv: command not found` (no pip-only install path)

The repository ships with `uv` as the recommended package manager,
but `pip` is fully supported. Use the `pip install -e .` editable
install shown above; `uv build` is **not** required for adopters
who only need to install the library.

### Windows multi-Python: `pip` resolves outside the virtualenv

On Windows, having multiple Python installations can leave `pip.exe`
pointing at the global interpreter even when a venv is active. Verify:

```powershell
Get-Command pip       # check the resolved path
Get-Command python    # check the resolved path (should be in .venv\Scripts)
```

If `pip` resolves outside the active venv, always invoke through the
venv's Python explicitly:

```powershell
python -m pip install -e "C:\path\to\tenantshield"
```

`python -m pip` uses the active interpreter's bundled pip, regardless
of which `pip.exe` is first in `PATH`.

### Venv created without pip (Microsoft Store Python, --without-pip)

Some Python distributions create venvs without bundling pip. Symptom:

```
No module named pip
```

Bootstrap pip into the venv with Python core's built-in `ensurepip`:

```powershell
python -m ensurepip --upgrade
python -m pip --version    # verify pip is now in the venv
```

Then proceed with the editable install above.

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
