# TenantShield Django Example

Runnable mini-project demonstrating TenantShield's multi-tenant
isolation end-to-end with Django + Django REST Framework.

## What this example demonstrates

This example shows TenantShield's three-layer enforcement (DR-019
triple defense) working together in a real Django + DRF application:

1. **`TenantContextMiddleware`** extracts the tenant ID from the
   `X-Tenant-Id` HTTP header on each request and binds it to the
   current scope.

2. **`@tenant_aware` decorator** on `Invoice` and `Org` models installs
   a manager that filters all queries by the active tenant ID, plus
   signal handlers that validate writes.

3. **DRF adapter** (three independent layers):
   - `IsSameTenant` permission: rejects requests without an active
     tenant scope (request-level) and rejects access to objects from
     other tenants (object-level).
   - `TenantAwareViewSetMixin`: queryset-level guard. With
     `@tenant_aware` models the manager already filters; the mixin
     acts as defense in depth.
   - `TenantValidatedSerializerMixin`: write-path validation. Auto-
     injects `tenant_id` from the active scope on create; rejects
     mismatched `tenant_id` on create/update with HTTP 403.

## Prerequisites

- Python 3.11 or newer.
- `uv` (recommended), or `pip` + `venv`.

## Setup

```bash
cd examples/01_django
uv venv .venv
# Activate the venv:
#   Linux/macOS:  source .venv/bin/activate
#   Windows:      .venv\Scripts\activate
uv pip install -e .
python manage.py makemigrations example_app
python manage.py migrate
python manage.py runserver
```

The editable install resolves `tenantshield` from the local source
tree (`../..`), installs `[django, jwt, drf]` extras, and pins
Django 5.2.x and DRF 3.17.x. After `runserver`, the API is available
at `http://localhost:8000`.

## Walkthrough -- curl commands

Open a second terminal. The following commands demonstrate
multi-tenant isolation.

### 1. Create invoices for two different tenants

```bash
# Create invoices for tenant 'acme'
curl -X POST http://localhost:8000/api/invoices/ \
    -H "X-Tenant-Id: acme" \
    -H "Content-Type: application/json" \
    -d '{"amount": 100, "description": "Acme invoice 1"}'
# Expected: 201 Created, JSON with tenant_id='acme' auto-injected.

curl -X POST http://localhost:8000/api/invoices/ \
    -H "X-Tenant-Id: acme" \
    -H "Content-Type: application/json" \
    -d '{"amount": 200, "description": "Acme invoice 2"}'

# Create invoice for tenant 'globex'
curl -X POST http://localhost:8000/api/invoices/ \
    -H "X-Tenant-Id: globex" \
    -H "Content-Type: application/json" \
    -d '{"amount": 999, "description": "Globex invoice 1"}'
```

### 2. List invoices -- each tenant sees only their own

```bash
# Tenant 'acme' sees 2 invoices
curl http://localhost:8000/api/invoices/ -H "X-Tenant-Id: acme"
# Expected: array of 2 invoices, all with tenant_id='acme'.

# Tenant 'globex' sees 1 invoice
curl http://localhost:8000/api/invoices/ -H "X-Tenant-Id: globex"
# Expected: array of 1 invoice with tenant_id='globex'.
```

### 3. Cross-tenant access attempt returns 404

```bash
# Get the PK of an acme invoice from previous list response
ACME_PK=1  # adjust based on actual PK

# Try to access from globex tenant
curl http://localhost:8000/api/invoices/$ACME_PK/ \
    -H "X-Tenant-Id: globex"
# Expected: 404 Not Found. The manager filters by tenant; the object
# doesn't exist in globex's queryset.
```

### 4. Attempt to create invoice for a different tenant returns 403

```bash
# In tenant 'acme' scope, try to create with explicit tenant_id='globex'
curl -X POST http://localhost:8000/api/invoices/ \
    -H "X-Tenant-Id: acme" \
    -H "Content-Type: application/json" \
    -d '{"tenant_id": "globex", "amount": 500, "description": "should fail"}'
# Expected: 403 Forbidden. TenantValidatedSerializerMixin detects the
# mismatch and raises TenantPermissionDenied.
```

### 5. Missing tenant header returns 500

```bash
# No X-Tenant-Id header at all
curl http://localhost:8000/api/invoices/
# Expected: 500 Internal Server Error. The middleware is configured
# with on_missing_tenant='raise'. Production deployments may prefer
# 'return_none' (empty results) or '404' (hide endpoint existence).
```

## Architecture notes

This example wires together:

- **`example_project/settings.py`**: declares `TenantContextMiddleware`
  in MIDDLEWARE + `TENANTSHIELD` config dict (extraction strategy =
  header, header name = `X-Tenant-Id`).
- **`example_app/models.py`**: `Invoice` and `Org` decorated with
  `@tenant_aware`.
- **`example_app/viewsets.py`**: ViewSets consume
  `TenantAwareViewSetMixin` + `IsSameTenant` permission.
- **`example_app/serializers.py`**: Serializers consume
  `TenantValidatedSerializerMixin`.

The four-layer chain (middleware -> permission -> mixin -> serializer)
provides defense in depth: a bug in any single layer is caught by the
others before tenant isolation is broken.

## Common gotchas

### `queryset = Model.objects.all()` as class attribute breaks

Don't do this:
```python
class InvoiceViewSet(TenantAwareViewSetMixin, ModelViewSet):
    queryset = Invoice.objects.all()  # FAILS at class load time
```

Class attributes are evaluated when the class is defined, when no
tenant scope is active. The `@tenant_aware` manager raises
`MissingTenantContextError` immediately. Use the lazy pattern:

```python
class InvoiceViewSet(TenantAwareViewSetMixin, ModelViewSet):
    def get_queryset(self):
        return Invoice.objects.all()  # eval per-request, scope active
```

### `_base_manager` bypasses reads, not writes

`Model._base_manager.all()` bypasses the `@tenant_aware` manager's
queryset filtering, but does NOT bypass the `pre_save` / `pre_delete`
signal handlers that enforce tenant coherence on writes. This is
deliberate: reads can opt out, writes cannot.

### MRO order matters

TenantShield mixins must come FIRST in the MRO chain:

```python
# Correct
class InvoiceSerializer(
    TenantValidatedSerializerMixin,
    serializers.ModelSerializer,
):
    ...

# Incorrect -- mixin is shadowed
class InvoiceSerializer(
    serializers.ModelSerializer,
    TenantValidatedSerializerMixin,
):
    ...
```

## Customize and experiment

Try modifying `example_project/settings.py`:

- Change `'on_missing_tenant'` to `'404'` and observe the missing-
  header response change to 404.
- Change `'on_missing_tenant'` to `'return_none'` and observe the
  list endpoint return an empty list instead of erroring.
- Switch `'tenant_extraction'` to `'subdomain'` and adjust your local
  hosts file to test subdomain-based tenancy.

## Files reference

```
examples/01_django/
├── pyproject.toml         Dependencies + editable install config
├── manage.py              Django management entry point
├── README.md              This file
├── example_project/       Project settings + URL routing
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── example_app/           Application code
    ├── models.py          Invoice + Org with @tenant_aware
    ├── serializers.py     Serializers with TenantValidatedSerializerMixin
    ├── viewsets.py        ViewSets with TenantAwareViewSetMixin + IsSameTenant
    └── urls.py            DRF DefaultRouter routes
```

## Related documentation

- [TenantShield README](../../README.md) -- project root.
- [Architecture Decision Records](../../docs/adr/) -- design decisions.
- [CHANGELOG](../../CHANGELOG.md) -- DR-019 triple defense rationale.
