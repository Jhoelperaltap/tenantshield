# Empirical smoke evidence -- Sub-phase 2C pre-kickoff

Date: 2026-05-15.
Repository HEAD at execution: `17213c2` (post-2B consolidation, roadmap v1.6).
Python version: 3.13.x (from lockfile).

## Purpose

Per Rule 40 (smoke scripts are specs subject to sec 6 num 39), this
document archives the empirical smoke executed before ratifying the
PHASE_2C_KICKOFF.md scope.

The smoke validates three architectural premises that drive Sub-fase 2C:

1. Django 6.0 works with TenantShield's adapter (Block C foundation).
2. django-stubs 6.0.x types cleanly against the adapter.
3. Cross-version compatibility (Django 4.2 + django-stubs 6.0.x) is
   empirically functional (ratifies B+D stubs strategy, ADR-0003).

## Component 1 -- Django 6.0.4 with TenantShield (current stubs)

### Shell commands

```bash
uv pip install "django==6.0.4" --no-deps --reinstall
uv run python -c "import django; print('Django:', django.__version__)"
uv run pytest
```

### Output

```
Django: 6.0.4
[...]
TOTAL  621  1  102  0  99.86%
228 passed, 2 deselected in 13.55s
```

Exit code 0.

## Component 2 -- Django 6.0.4 + django-stubs 6.0.3

### Shell commands

```bash
uv pip install "django==6.0.4" --no-deps --reinstall
uv pip install "django-stubs[compatible-mypy]==6.0.3" --no-deps --reinstall
uv run mypy src/tenantshield
```

### Output

```
Success: no issues found in 23 source files
```

Exit code 0.

## Component 3 (CRITICAL) -- Django 4.2.30 + django-stubs 6.0.3

### Shell commands

```bash
uv pip install "django==4.2.30" --no-deps --reinstall
uv pip install "django-stubs[compatible-mypy]==6.0.3" --no-deps --reinstall
uv run mypy src/tenantshield
uv run pytest
```

### Output

```
Success: no issues found in 23 source files
[...]
228 passed, 2 deselected in 4.84s
```

mypy exit 0 + pytest exit 0.

## Component 4 -- pytest-django with Django 6.0.4

Implicit in Component 1. pytest-django 4.12.0 ran all 228 tests against
Django 6.0.4 without compatibility warnings.

## State recovery

```bash
uv pip install "django==5.2.14" --no-deps --reinstall
uv pip install "django-stubs[compatible-mypy]==5.2.9" --no-deps --reinstall
uv sync --all-extras --dev
```

Result: lockfile restored to canonical state. `git diff uv.lock` empty.
`git status` clean. pytest sanity post-restore: 228 passed.

## Verdict

B+D stubs strategy ratified empirically. Component 3 disipa el riesgo
critico: stubs 6.0.3 NO rompen compat con Django 4.2.30 en este
adapter. Pin unico loose `django-stubs[compatible-mypy]>=6.0,<7.0` es
viable + ADR-0003 documenta la decision consciente sobre soporte 4.2
empirico.

## Five architectural premises validated for 2C

1. Django 6.0.4 funciona con TenantShield actual sin cambios al adapter.
2. django-stubs 6.0.3 typing limpio sobre el adapter.
3. Cross-version compat (4.2 + 6.0) con stubs 6.0.x funciona empiricamente.
4. pytest-django 4.12.0 transparente con Django 6.0.
5. Recovery clean del state via `uv sync --all-extras --dev`.

## References

- `PHASE_2C_KICKOFF.md` section 0 (this evidence's primary consumer).
- ADR-0003 (`docs/adr/0003-django-4-2-empirical-support.md`, materialized
  in Tarea 2C.0).
- Roadmap v1.6 section 6 Rule 40 (smoke scripts as specs).
