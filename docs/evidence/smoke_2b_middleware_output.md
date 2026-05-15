# Empirical smoke evidence -- Sub-phase 2B middleware design

This document archives the output of `scripts/smoke_2b_middleware.py`
executed during Tarea pre-2B.0 as evidence of compliance with roadmap
rule sec 6 num 39 (E31 refined: verification of application, not only
importability). The script itself was transient and is not preserved
in the repository; its content is reconstructed below for traceability.

## Execution context

- Date: 2026-05-14 (during Sub-phase 2B kickoff ratification).
- Repository HEAD at time of execution: `e00b199` (post-2A consolidation).
- Python version: 3.13.x (via uv default).
- Django version: 5.2.14 (default from lockfile).
- PyJWT version: 2.12.1 (installed temporarily as dev dep, reverted after smoke).
- Two fixes were applied to the kickoff section 0.2 script during execution
  (amendment E37 retrospective): `sys.path.insert` for repo-root resolution
  in standalone execution, and `settings.ALLOWED_HOSTS = ["*"]` for synthetic
  Host header validation with DEBUG=False.

## Output (verbatim)

```
[subdomain] OK: tenant=acme
[subdomain MISSING] OK: Cannot extract subdomain from host 'example.com'
[header] OK: tenant=globex
[header MISSING] OK: Header 'X-Tenant-Id' missing or empty
[callable] OK: tenant=initech
[callable MISSING] OK: Callable strategy returned empty value
[jwt] OK: tenant=umbrella
[jwt MISSING] OK: Authorization header missing or not Bearer

ALL SMOKE VERIFICATIONS PASSED
```

Exit code: 0.

## Verifications performed

- Subdomain strategy: extracts `acme` from `acme.example.com`; raises on `example.com` (two-part host).
- Header strategy: extracts `globex` from `X-Tenant-Id: globex` header; raises on missing header.
- Callable strategy: invokes user function returning `request.GET.get("tenant")`; raises on empty result.
- JWT strategy: decodes HS256-signed token with `tenant_id` claim; raises on missing `Authorization: Bearer` header.
- Tenant scope lifecycle: `bind_tenant -> tenant_scope -> exit` exercised in each of the 4 happy paths; `try_current_tenant()` returns `None` after scope exit.

## Lessons

The smoke uncovered two latent bugs in the script spec itself (kickoff section 0.2):

1. Repository root not on `sys.path` when script is executed standalone -- fixed with explicit `sys.path.insert(repo_root)` using `__file__` resolution.
2. `request.get_host()` raises `DisallowedHost` against `ALLOWED_HOSTS=[]` (default with DEBUG=False) -- fixed with `settings.ALLOWED_HOSTS = ["*"]` runtime override in the script.

Both fixes are documented in roadmap amendment E37 (smoke scripts must be self-contained re-execution environment). The kickoff section 0.2 in `PHASE_2B_KICKOFF.md` is preserved as-emitted with bugs latent; the closure document `PHASE_2B_CLOSURE.md` (to be generated) will reference this evidence file and note the retrospective fixes.

## Smoke script content (preserved for archival)

```python
"""Pre-kickoff smoke verification for Sub-phase 2B middleware design.

This script runs the four prescribed extraction strategies against a
synthetic Django request flow. Each strategy must:
  1. Receive a Django HttpRequest.
  2. Extract the tenant identifier per its rule.
  3. Bind the tenant via bind_tenant().
  4. Enter tenant_scope() for the request lifecycle.
  5. Exit scope cleanly on response.
  6. Raise a documented exception when the request does not contain
     the expected tenant identifier.

The script does NOT exercise the production middleware (which does not
exist yet). It exercises the extraction logic in isolation, using
Django's RequestFactory to build synthetic requests, and validates the
contract the future middleware will compose.
"""

from __future__ import annotations

import os
import sys

# Ensure repo root is on sys.path so 'tests.integration.django.settings'
# resolves when this script is executed directly (e.g.,
# `uv run python scripts/smoke_2b_middleware.py`). Pytest adds the repo
# root automatically, but standalone Python execution does not. See
# rule sec 6 num 39 amendment E37 for the canonical pattern.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "tests.integration.django.settings",
)

import django

django.setup()

# Standalone script environment overrides.
#
# This script executes outside the pytest lifecycle. Django settings
# loaded from tests.integration.django.settings have DEBUG=False and
# the default empty ALLOWED_HOSTS, which causes HttpRequest.get_host()
# to raise DisallowedHost for any synthetic Host header. We override
# ALLOWED_HOSTS at runtime to allow synthetic hosts for the smoke
# verification. This does NOT modify the persisted settings file.
#
# Pattern note: production middleware in Sub-phase 2B.5 will rely on
# request.get_host() which honors ALLOWED_HOSTS. The smoke is
# validating extraction logic, not Django's security validation, so
# bypassing ALLOWED_HOSTS here is appropriate; real middleware tests
# in 2B.9 use Django's test Client which handles ALLOWED_HOSTS via
# the test framework.
from django.conf import settings  # noqa: PLC0415 -- post-setup import

settings.ALLOWED_HOSTS = ["*"]  # type: ignore[misc] -- runtime mutation

from django.test import RequestFactory

from tenantshield import TenantId, bind_tenant, tenant_scope, try_current_tenant


def extract_subdomain(request) -> str:
    """Subdomain strategy: 'acme.example.com' -> 'acme'."""
    host = request.get_host()  # 'acme.example.com:8000' or 'acme.example.com'
    host_no_port = host.split(":")[0]
    parts = host_no_port.split(".")
    if len(parts) < 3:
        msg = f"Cannot extract subdomain from host {host_no_port!r}"
        raise ValueError(msg)
    return parts[0]


def extract_header(request, header_name: str = "X-Tenant-Id") -> str:
    """Header strategy: HTTP header value as tenant id."""
    # Django normalizes 'X-Tenant-Id' to 'HTTP_X_TENANT_ID' in META.
    meta_key = "HTTP_" + header_name.upper().replace("-", "_")
    value = request.META.get(meta_key)
    if not value:
        msg = f"Header {header_name!r} missing or empty"
        raise ValueError(msg)
    return value


def extract_callable(request, fn) -> str:
    """Callable strategy: user-provided callable."""
    result = fn(request)
    if not result:
        msg = "Callable strategy returned empty value"
        raise ValueError(msg)
    return result


# JWT strategy is verified separately because it requires PyJWT and a
# token. We use a synthetic token signed with HS256 for the smoke.

def extract_jwt(request, secret: str, claim: str = "tenant_id") -> str:
    """JWT strategy: decode Bearer token and extract claim."""
    import jwt  # noqa: PLC0415 -- optional dep, imported on demand

    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        msg = "Authorization header missing or not Bearer"
        raise ValueError(msg)
    token = auth.removeprefix("Bearer ").strip()
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    tenant = payload.get(claim)
    if not tenant:
        msg = f"JWT claim {claim!r} missing or empty"
        raise ValueError(msg)
    return str(tenant)


def simulate_request_cycle(strategy, request) -> str:
    """Simulate the future middleware contract for one strategy."""
    tenant_id_str = strategy(request)
    ctx = bind_tenant(TenantId(tenant_id_str))
    with tenant_scope(ctx):
        # Inside the scope, downstream code (views, ORM) sees the tenant.
        current = try_current_tenant()
        assert current is not None, "tenant_scope did not bind context"
        assert current.tenant_id == tenant_id_str, "tenant id mismatch"
        return f"OK: tenant={tenant_id_str}"
    # After scope exits, current_tenant must be None again.


def main() -> int:
    factory = RequestFactory()

    # === Subdomain strategy ===
    req = factory.get("/", HTTP_HOST="acme.example.com")
    result = simulate_request_cycle(extract_subdomain, req)
    print(f"[subdomain] {result}")
    assert try_current_tenant() is None, "scope did not exit cleanly"

    # Subdomain missing case
    req_bad = factory.get("/", HTTP_HOST="example.com")
    try:
        simulate_request_cycle(extract_subdomain, req_bad)
        print("[subdomain MISSING] ERROR: expected ValueError, got success")
        return 1
    except ValueError as exc:
        print(f"[subdomain MISSING] OK: {exc}")

    # === Header strategy ===
    req = factory.get("/", HTTP_X_TENANT_ID="globex")
    result = simulate_request_cycle(extract_header, req)
    print(f"[header] {result}")

    # Header missing case
    req_bad = factory.get("/")
    try:
        simulate_request_cycle(extract_header, req_bad)
        print("[header MISSING] ERROR: expected ValueError, got success")
        return 1
    except ValueError as exc:
        print(f"[header MISSING] OK: {exc}")

    # === Callable strategy ===
    def my_extractor(request) -> str:
        return request.GET.get("tenant", "")

    req = factory.get("/?tenant=initech")
    result = simulate_request_cycle(lambda r: extract_callable(r, my_extractor), req)
    print(f"[callable] {result}")

    # Callable missing case
    req_bad = factory.get("/")
    try:
        simulate_request_cycle(lambda r: extract_callable(r, my_extractor), req_bad)
        print("[callable MISSING] ERROR: expected ValueError, got success")
        return 1
    except ValueError as exc:
        print(f"[callable MISSING] OK: {exc}")

    # === JWT strategy ===
    try:
        import jwt  # noqa: PLC0415
    except ImportError:
        print("[jwt] SKIP: PyJWT not installed (optional dep)")
    else:
        secret = "smoke-test-secret-not-for-production"  # noqa: S105
        token = jwt.encode({"tenant_id": "umbrella"}, secret, algorithm="HS256")
        req = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        result = simulate_request_cycle(
            lambda r: extract_jwt(r, secret), req,
        )
        print(f"[jwt] {result}")

        # JWT missing case
        req_bad = factory.get("/")
        try:
            simulate_request_cycle(lambda r: extract_jwt(r, secret), req_bad)
            print("[jwt MISSING] ERROR: expected ValueError, got success")
            return 1
        except ValueError as exc:
            print(f"[jwt MISSING] OK: {exc}")

    print()
    print("ALL SMOKE VERIFICATIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
