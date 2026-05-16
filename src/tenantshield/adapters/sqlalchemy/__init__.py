"""TenantShield SQLAlchemy adapter.

Provides multi-tenant ORM enforcement for SQLAlchemy 2.0+ models via:

- ``@tenant_aware`` decorator on declarative model classes.
- Event listeners for write-time enforcement (``before_insert``,
  ``before_update``, ``before_delete``).
- ``do_orm_execute`` session-level event for read-time filtering.
- ``SessionScope`` context manager for tenant-bound session
  operations (Sub-fase 3B).

This adapter targets SQLAlchemy 2.0+ only (see ADR-0006 for rationale).
Adopters running SQLAlchemy 1.4 must upgrade to 2.0 before using
this adapter.

Public surface
--------------

- :func:`tenant_aware` -- decorator applied to declarative models.
- :func:`SessionScope` -- context manager for tenant-bound session
  operations.

Exceptions (re-exported from core):

- :class:`MissingTenantContextError`.
- :class:`CrossTenantAccessError`.
"""

from __future__ import annotations

from tenantshield.adapters.sqlalchemy.decorator import tenant_aware
from tenantshield.adapters.sqlalchemy.exceptions import (
    CrossTenantAccessError,
    MissingTenantContextError,
)
from tenantshield.adapters.sqlalchemy.lifecycle import SessionScope

# middleware.TenantSessionMiddleware exported in Tareas 3B.3-4.

__all__ = [
    "CrossTenantAccessError",
    "MissingTenantContextError",
    "SessionScope",
    "tenant_aware",
]
