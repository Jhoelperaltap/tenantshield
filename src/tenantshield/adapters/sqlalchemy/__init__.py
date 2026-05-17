"""TenantShield SQLAlchemy adapter.

Provides multi-tenant ORM enforcement for SQLAlchemy 2.0+ models via:

- ``@tenant_aware`` decorator on declarative model classes.
- Event listeners for write-time enforcement (``before_insert``,
  ``before_update``, ``before_delete``).
- ``do_orm_execute`` session-level event for read-time filtering.
- ``SessionScope`` context manager for tenant-bound session
  operations (Sub-fase 3B).
- ``AsyncSessionScope`` async context manager for tenant-bound
  ``AsyncSession`` operations (Sub-fase 4A).
- ``bind_async_session_to_tenant`` explicit async tenant binding
  helper (Sub-fase 4A).
- ``bind_session_to_tenant`` explicit tenant binding helper
  (Sub-fase 3B).
- ``TenantSessionMiddleware`` ASGI middleware (Sub-fase 3B).
- ``TenantSessionMiddlewareWSGI`` WSGI middleware (Sub-fase 3B).

This adapter targets SQLAlchemy 2.0+ only (see ADR-0006 for rationale).
Adopters running SQLAlchemy 1.4 must upgrade to 2.0 before using
this adapter.

Public surface
--------------

- :func:`tenant_aware` -- decorator applied to declarative models.
- :func:`SessionScope` -- context manager for tenant-bound sync
  ``Session`` operations.
- :func:`AsyncSessionScope` -- async context manager for tenant-bound
  ``AsyncSession`` operations.
- :func:`bind_async_session_to_tenant` -- explicit async tenant binding
  helper.
- :func:`bind_session_to_tenant` -- explicit tenant binding helper.
- :class:`TenantSessionMiddleware` -- ASGI middleware wrapping
  request handling with tenant scope.
- :class:`TenantSessionMiddlewareWSGI` -- WSGI middleware wrapping
  request handling with tenant scope; generator-based body
  iteration preserves scope through lazy chunks.

Exceptions (re-exported from core):

- :class:`MissingTenantContextError`.
- :class:`CrossTenantAccessError`.
"""

from __future__ import annotations

from tenantshield.adapters.sqlalchemy.async_lifecycle import (
    AsyncSessionScope,
    bind_async_session_to_tenant,
)
from tenantshield.adapters.sqlalchemy.decorator import tenant_aware
from tenantshield.adapters.sqlalchemy.exceptions import (
    CrossTenantAccessError,
    MissingTenantContextError,
)
from tenantshield.adapters.sqlalchemy.lifecycle import (
    SessionScope,
    bind_session_to_tenant,
)
from tenantshield.adapters.sqlalchemy.middleware import (
    TenantSessionMiddleware,
    TenantSessionMiddlewareWSGI,
)

__all__ = [
    "AsyncSessionScope",
    "CrossTenantAccessError",
    "MissingTenantContextError",
    "SessionScope",
    "TenantSessionMiddleware",
    "TenantSessionMiddlewareWSGI",
    "bind_async_session_to_tenant",
    "bind_session_to_tenant",
    "tenant_aware",
]
