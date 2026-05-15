"""SQLAlchemy event listener registration for tenant enforcement.

Registers event listeners on tenant-aware model classes to enforce
multi-tenant isolation at write time and read time.

Write enforcement (this module):

- ``before_insert``: auto-inject ``tenant_id`` from active scope if
  unset; validate match if explicitly set. Materialization in
  Tarea 3A.3 (this commit). Partial DR-021.
- ``before_update``: prevent cross-tenant updates. Materialization in
  Tarea 3A.4. Completes DR-021.
- ``before_delete``: prevent cross-tenant deletes. Materialization in
  Tarea 3A.4. Completes DR-021.

Read enforcement:

- ``do_orm_execute``: filter SELECT queries by active tenant scope.
  Materialization in Tarea 3A.5. DR-022.

Pattern follows Django adapter ``signals.py`` precedent: same exception
constructors, same ``TenantContext`` access pattern via
``try_current_tenant()``. This preserves cross-adapter mental model
coherence for adopters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import event

from tenantshield import TenantId, try_current_tenant
from tenantshield.exceptions import (
    CrossTenantAccessError,
    MissingTenantContextError,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.orm import Mapper


_TENANT_ID_COLUMN_NAME = "tenant_id"


def _before_insert_handler(
    mapper: Mapper[Any],
    connection: Connection,  # noqa: ARG001
    target: Any,  # noqa: ANN401
) -> None:
    """Enforce tenant context on INSERT operations.

    Behavior:

    1. If no active tenant scope: raise ``MissingTenantContextError``.
    2. If ``target.tenant_id`` is unset (None or falsy): auto-inject
       from active scope (``ctx.tenant_id``).
    3. If ``target.tenant_id`` is set: validate match with
       ``ctx.tenant_id``; raise ``CrossTenantAccessError`` on mismatch.

    Pattern matches Django adapter
    ``signals._validate_tenant_coherence``.

    Args:
        mapper: SQLAlchemy Mapper for the model class (provided by
            event).
        connection: Active DB connection (provided by event; unused).
        target: Model instance being inserted.

    Raises:
        MissingTenantContextError: If no active tenant scope is bound
            when INSERT fires.
        CrossTenantAccessError: If ``target.tenant_id`` is set and does
            not match active scope.
    """
    ctx = try_current_tenant()
    if ctx is None:
        raise MissingTenantContextError(
            operation=f"before_insert.{mapper.class_.__qualname__}",
            stack_context={
                "hint": "No tenant context active for INSERT operation.",
            },
        )

    target_tenant = getattr(target, _TENANT_ID_COLUMN_NAME, None)

    if not target_tenant:
        setattr(target, _TENANT_ID_COLUMN_NAME, ctx.tenant_id)
        return

    if str(target_tenant) != str(ctx.tenant_id):
        raise CrossTenantAccessError(
            tenant_id_expected=ctx.tenant_id,
            tenant_id_actual=TenantId(str(target_tenant)),
            model=mapper.class_.__qualname__,
            operation=f"before_insert.{mapper.class_.__qualname__}",
        )


def register_write_enforcement(cls: type) -> None:
    """Register write-path event listeners on a tenant-aware model class.

    Invoked by the ``@tenant_aware`` decorator at class-definition time
    to attach event listeners for INSERT enforcement.

    UPDATE + DELETE listener registration deferred to Tarea 3A.4.

    Args:
        cls: SQLAlchemy declarative model class marked as tenant-aware.
    """
    event.listen(cls, "before_insert", _before_insert_handler)
