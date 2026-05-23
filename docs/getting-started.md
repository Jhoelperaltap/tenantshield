# Getting Started

## Installation

The supported install paths during the alpha series:

### From TestPyPI (recommended for cohort adopters from v0.6.0-alpha onward)

```bash
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            tenantshield
```

Or with `uv`:

```bash
uv add tenantshield --index https://test.pypi.org/simple/
```

The TestPyPI publication is automated via GitHub Actions on each tag
push (see [`.github/workflows/publish-testpypi.yml`](https://github.com/Jhoelperaltap/tenantshield/blob/main/.github/workflows/publish-testpypi.yml)).
Until `v1.0.0` ships to public PyPI, TestPyPI is the canonical
distribution channel for alpha releases.

#### Best practice: `explicit = true` in `[[tool.uv.index]]`

When integrating TestPyPI as a package source via `uv` configuration
(not just the one-off `--index` flag), the adopter SHOULD configure
the index with `explicit = true` to isolate TestPyPI consultation to
TenantShield only:

```toml
# In adopter's pyproject.toml:

[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
explicit = true  # CRITICAL: required for clean transitive dep resolution

[project]
dependencies = [
    "tenantshield==0.6.0a0",
    # ... other dependencies resolved from PyPI public
]

[tool.uv.sources]
tenantshield = { index = "testpypi" }
```

**Why `explicit = true` is critical:** Without it, `uv` consults
TestPyPI for the *entire* dependency tree. TestPyPI is a staging
index — it does not host the full transitive surface that PyPI
public does (e.g., `cryptography`, `pydantic`). The resolver breaks
with missing transitive deps.

`explicit = true` scopes TestPyPI consultation to packages explicitly
listed in `[tool.uv.sources]` while letting `uv` resolve everything
else from PyPI public. The result is a clean lockfile that pins
TenantShield from TestPyPI and all transitives from PyPI.

This pattern was discovered empirically by Counterbook (TenantShield
reference adopter, mini-ticket #011) during the v0.6.0-alpha TestPyPI
cutover. The same pattern applies to any adopter consuming TenantShield
from TestPyPI until the v1.0.0 public PyPI release.

### From a GitHub tag (alternative for pre-`v0.6.0-alpha` versions)

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

## SQLAlchemy adapter: `with_for_update()` interaction

SQLAlchemy adopters frequently use `Query.with_for_update()` (the
SA equivalent of Django's `select_for_update()`) to acquire row
locks during read-modify-write workflows. The interaction with
TenantShield's enforcement layer is straightforward but worth
documenting explicitly so the adopter does not assume the lock
acquisition is a bypass surface.

**Pattern**:

```python
from sqlalchemy.orm import Session

with tenant_scope(bind_tenant(TenantId("acme"))):
    with Session(engine) as session:
        bind_session_to_tenant(session, current_tenant())
        # with_for_update() preserves the tenant filter applied at
        # query construction; the SELECT ... FOR UPDATE clause carries
        # WHERE tenant_id = 'acme' just like any other scoped query.
        invoice = (
            session.query(Invoice)
            .filter(Invoice.id == 42)
            .with_for_update()
            .one()
        )
        invoice.amount = 999
        session.commit()
```

**Two facts to anchor**:

1. **Tenant scope is applied at query construction**, not at lock
   acquisition. The `WHERE tenant_id = <ctx>` clause is added by
   the bound Session's `do_orm_execute` event listener; the lock
   is an attribute of the SQL statement that the query builder
   emits. Both compose orthogonally.
2. **Cross-tenant attempts during the locked operation still
   raise**. If the same caller attempted
   `session.query(Invoice).filter(Invoice.id == 42).with_for_update().one()`
   with `id=42` belonging to tenant `globex` instead of `acme`, the
   SQL would return zero rows (the tenant filter narrows). If the
   caller then attempted to `UPDATE` on a manually-constructed
   cross-tenant target, the `before_update` event listener would
   raise `CrossTenantAccessError` before the SQL executes — see
   [Security posture §SQLAlchemy](concepts/security-posture.md#sqlalchemy-adapter-security-posture)
   for the always-on pre-SQL enforcement model.

Unlike Django's `select_for_update()` (which interacts with the
`TenantAwareQuerySet`'s manager filter at the queryset level), SA's
`with_for_update()` interacts with the `do_orm_execute` event
listener at the SQL emission level. The architectural surfaces
differ but the security guarantee is the same: lock acquisition
does not bypass tenant enforcement.

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
