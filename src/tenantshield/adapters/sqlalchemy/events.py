"""SQLAlchemy event listener registration for tenant enforcement.

Registers event listeners on tenant-aware model classes to enforce
multi-tenant isolation at write time and read time.

Write enforcement (DR-021, complete):

- ``before_insert``: auto-inject ``tenant_id`` from active scope if
  unset; validate match if explicitly set. Materialized in Tarea 3A.3.
- ``before_update``: prevent cross-tenant updates. Materialized in
  Tarea 3A.4.
- ``before_delete``: prevent cross-tenant deletes. Materialized in
  Tarea 3A.4.

Read enforcement (DR-022, complete):

- ``do_orm_execute``: filter SELECT queries by active tenant scope via
  ``with_loader_criteria`` injection. Discovers tenant-aware models
  via ``__tenantshield_tenant_aware__`` sentinel attribute. Falls
  through (returns unfiltered) when no active scope; stricter
  raise-on-missing behavior is provided by middleware in Sub-fase 3B.
  Materialized in Tarea 3A.5.

Pattern follows Django adapter ``signals.py`` precedent for writes:
same exception constructors, same ``TenantContext`` access pattern via
``try_current_tenant()``. For reads, SA uses event-based filtering via
``with_loader_criteria`` whereas Django uses a custom Manager class;
this is the conceptual analog within each ORM's event model. See
ADR-0007 for full rationale.

The ``_TENANT_AWARE_SENTINEL`` constant is defined here (not in the
decorator module) because both the decorator and the
``do_orm_execute`` handler need it, and locating it here gives a
single-direction dependency: ``decorator.py -> events.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from tenantshield import TenantId, try_current_tenant
from tenantshield.audit import (
    AuditEvent,
    AuditEventType,
)
from tenantshield.audit import emit as audit_emit
from tenantshield.exceptions import (
    CrossTenantAccessError,
    MissingTenantContextError,
)
from tenantshield.observability._emit import emit_event
from tenantshield.observability.events import (
    EVENT_READ_FALLTHROUGH,
    EVENT_READ_FILTERED,
    EVENT_WRITE_BLOCKED,
    EVENT_WRITE_INJECTED,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.orm import ORMExecuteState
    from sqlalchemy.orm.mapper import Mapper

    from tenantshield import TenantContext


_TENANT_ID_COLUMN_NAME = "tenant_id"
_TENANT_AWARE_SENTINEL = "__tenantshield_tenant_aware__"


def _emit_enforcement_violation_audit(
    ctx: TenantContext,
    attempted_tenant_id: str | None,
    mapper: Mapper[Any],
    operation: str,
) -> None:
    """Dispatch ``ENFORCEMENT_VIOLATION`` to the audit bus.

    Sub-fase 5B.5.1 dual-dispatch companion to the observability
    ``EVENT_WRITE_BLOCKED`` emission. Audit dispatch is gated by the
    sink registry (independent of observability ``configure``) per
    Decision 7-A separation.

    Args:
        ctx: Active tenant context bound at the time of the violation.
        attempted_tenant_id: The cross-tenant value the caller tried to
            write, or ``None`` for UPDATE/DELETE missing-tenant_id paths.
        mapper: SA mapper for the model class involved.
        operation: ``"before_insert"`` / ``"before_update"`` /
            ``"before_delete"``.
    """
    audit_emit(
        AuditEvent(
            event_type=AuditEventType.ENFORCEMENT_VIOLATION,
            tenant_context=ctx,
            payload={
                "attempted_tenant_id": attempted_tenant_id,
                "model_class": mapper.class_.__qualname__,
                "operation": operation,
            },
        )
    )


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
        emit_event(
            EVENT_WRITE_INJECTED,
            tenant_id=str(ctx.tenant_id),
            model_class=mapper.class_.__qualname__,
            operation="before_insert",
        )
        return

    if str(target_tenant) != str(ctx.tenant_id):
        emit_event(
            EVENT_WRITE_BLOCKED,
            tenant_id=str(ctx.tenant_id),
            attempted_tenant_id=str(target_tenant),
            model_class=mapper.class_.__qualname__,
            operation="before_insert",
        )
        _emit_enforcement_violation_audit(
            ctx=ctx,
            attempted_tenant_id=str(target_tenant),
            mapper=mapper,
            operation="before_insert",
        )
        raise CrossTenantAccessError(
            tenant_id_expected=ctx.tenant_id,
            tenant_id_actual=TenantId(str(target_tenant)),
            model=mapper.class_.__qualname__,
            operation=f"before_insert.{mapper.class_.__qualname__}",
        )


def _before_update_handler(
    mapper: Mapper[Any],
    connection: Connection,  # noqa: ARG001
    target: Any,  # noqa: ANN401
) -> None:
    """Enforce tenant context on UPDATE operations.

    Behavior:

    1. If no active tenant scope: raise ``MissingTenantContextError``.
    2. Validate ``target.tenant_id`` matches ``ctx.tenant_id``; raise
       ``CrossTenantAccessError`` on mismatch.

    Note: unlike INSERT, UPDATE never auto-injects. A tenant-aware row
    reaching UPDATE always had ``tenant_id`` set at INSERT time.
    Mismatch indicates either (a) cross-tenant write attempt or (b)
    tenant_id mutation, both prohibited.

    Pattern matches Django adapter
    ``signals._validate_tenant_coherence`` for the UPDATE path.

    Args:
        mapper: SQLAlchemy Mapper for the model class (provided by
            event).
        connection: Active DB connection (provided by event; unused).
        target: Model instance being updated.

    Raises:
        MissingTenantContextError: If no active tenant scope is bound
            when UPDATE fires.
        CrossTenantAccessError: If ``target.tenant_id`` does not match
            active scope (including missing tenant_id case).
    """
    ctx = try_current_tenant()
    if ctx is None:
        raise MissingTenantContextError(
            operation=f"before_update.{mapper.class_.__qualname__}",
            stack_context={
                "hint": "No tenant context active for UPDATE operation.",
            },
        )

    target_tenant = getattr(target, _TENANT_ID_COLUMN_NAME, None)

    if not target_tenant:
        emit_event(
            EVENT_WRITE_BLOCKED,
            tenant_id=str(ctx.tenant_id),
            attempted_tenant_id=None,
            model_class=mapper.class_.__qualname__,
            operation="before_update",
        )
        _emit_enforcement_violation_audit(
            ctx=ctx,
            attempted_tenant_id=None,
            mapper=mapper,
            operation="before_update",
        )
        raise CrossTenantAccessError(
            tenant_id_expected=ctx.tenant_id,
            tenant_id_actual=None,
            model=mapper.class_.__qualname__,
            operation=f"before_update.{mapper.class_.__qualname__}",
        )

    if str(target_tenant) != str(ctx.tenant_id):
        emit_event(
            EVENT_WRITE_BLOCKED,
            tenant_id=str(ctx.tenant_id),
            attempted_tenant_id=str(target_tenant),
            model_class=mapper.class_.__qualname__,
            operation="before_update",
        )
        _emit_enforcement_violation_audit(
            ctx=ctx,
            attempted_tenant_id=str(target_tenant),
            mapper=mapper,
            operation="before_update",
        )
        raise CrossTenantAccessError(
            tenant_id_expected=ctx.tenant_id,
            tenant_id_actual=TenantId(str(target_tenant)),
            model=mapper.class_.__qualname__,
            operation=f"before_update.{mapper.class_.__qualname__}",
        )


def _before_delete_handler(
    mapper: Mapper[Any],
    connection: Connection,  # noqa: ARG001
    target: Any,  # noqa: ANN401
) -> None:
    """Enforce tenant context on DELETE operations.

    Behavior:

    1. If no active tenant scope: raise ``MissingTenantContextError``.
    2. Validate ``target.tenant_id`` matches ``ctx.tenant_id``; raise
       ``CrossTenantAccessError`` on mismatch.

    Pattern matches Django adapter
    ``signals._validate_tenant_coherence`` for the DELETE path.

    Args:
        mapper: SQLAlchemy Mapper for the model class (provided by
            event).
        connection: Active DB connection (provided by event; unused).
        target: Model instance being deleted.

    Raises:
        MissingTenantContextError: If no active tenant scope is bound
            when DELETE fires.
        CrossTenantAccessError: If ``target.tenant_id`` does not match
            active scope (including missing tenant_id case).
    """
    ctx = try_current_tenant()
    if ctx is None:
        raise MissingTenantContextError(
            operation=f"before_delete.{mapper.class_.__qualname__}",
            stack_context={
                "hint": "No tenant context active for DELETE operation.",
            },
        )

    target_tenant = getattr(target, _TENANT_ID_COLUMN_NAME, None)

    if not target_tenant:
        emit_event(
            EVENT_WRITE_BLOCKED,
            tenant_id=str(ctx.tenant_id),
            attempted_tenant_id=None,
            model_class=mapper.class_.__qualname__,
            operation="before_delete",
        )
        _emit_enforcement_violation_audit(
            ctx=ctx,
            attempted_tenant_id=None,
            mapper=mapper,
            operation="before_delete",
        )
        raise CrossTenantAccessError(
            tenant_id_expected=ctx.tenant_id,
            tenant_id_actual=None,
            model=mapper.class_.__qualname__,
            operation=f"before_delete.{mapper.class_.__qualname__}",
        )

    if str(target_tenant) != str(ctx.tenant_id):
        emit_event(
            EVENT_WRITE_BLOCKED,
            tenant_id=str(ctx.tenant_id),
            attempted_tenant_id=str(target_tenant),
            model_class=mapper.class_.__qualname__,
            operation="before_delete",
        )
        _emit_enforcement_violation_audit(
            ctx=ctx,
            attempted_tenant_id=str(target_tenant),
            mapper=mapper,
            operation="before_delete",
        )
        raise CrossTenantAccessError(
            tenant_id_expected=ctx.tenant_id,
            tenant_id_actual=TenantId(str(target_tenant)),
            model=mapper.class_.__qualname__,
            operation=f"before_delete.{mapper.class_.__qualname__}",
        )


def _do_orm_execute_handler(orm_execute_state: ORMExecuteState) -> None:
    """Filter SELECT queries by active tenant scope for tenant-aware models.

    Behavior:

    1. If statement is not a SELECT or not ORM-statement: skip (pass
       through unchanged).
    2. If no active tenant scope: skip filtering (read-without-scope
       returns unfiltered results; stricter raise-on-missing behavior
       provided by middleware in Sub-fase 3B per DR-016 config).
    3. For each tenant-aware entity in the statement (discovered via
       ``__tenantshield_tenant_aware__`` sentinel attribute on the
       entity class), inject a ``with_loader_criteria`` option that
       filters ``tenant_id == ctx.tenant_id``.

    Uses a static SQL expression (``entity.tenant_id == tenant``)
    rather than a Python lambda. SA caches loader-criteria lambdas
    based on the lambda body and ignores closure variables by default,
    so a lambda capturing the runtime tenant would be reused with the
    wrong tenant on subsequent queries. The static expression is
    rebuilt per invocation and binds the current tenant correctly.

    Args:
        orm_execute_state: SQLAlchemy ORMExecuteState provided by the
            ``do_orm_execute`` event. Contains the statement being
            executed plus metadata (``is_select``, ``is_orm_statement``,
            ``column_descriptions``).
    """
    if not (orm_execute_state.is_select and orm_execute_state.is_orm_statement):
        return

    ctx = try_current_tenant()
    if ctx is None:
        emit_event(
            EVENT_READ_FALLTHROUGH,
            operation="do_orm_execute",
        )
        return

    tenant = str(ctx.tenant_id)

    # ``column_descriptions`` is a Select-specific attribute; the
    # ``is_select`` + ``is_orm_statement`` guard above narrows the
    # statement to a Select at runtime, but the static type
    # ``Executable`` on ``orm_execute_state.statement`` cannot reflect
    # that. The chain of ``Unknown`` types from SA's internal API is
    # the same Sub-fase 2A precedent as ``django-stubs`` access to
    # ``cls._meta``: documented public-by-contract, untyped at the
    # checker level.
    statement: Any = orm_execute_state.statement
    for col_desc in statement.column_descriptions:
        entity = col_desc.get("entity")
        # Defensive null-check: SQLAlchemy 2.0+ canonical usage populates
        # ``column_descriptions[i]["entity"]`` for every entry, including
        # function/literal selects (entity points to the source mapped
        # class). The ``None`` branch documents the API contract surface
        # (``get`` returns ``None`` when key absent) but is empirically
        # unreachable through SA 2.0+ ORM SELECT paths. Rule 28 authorizes
        # pragma on defensive branches that document a contract rather
        # than implement reachable logic.
        if entity is None:  # pragma: no cover
            continue
        if not getattr(entity, _TENANT_AWARE_SENTINEL, False):
            continue

        orm_execute_state.statement = statement.options(
            with_loader_criteria(
                entity,
                entity.tenant_id == tenant,
                include_aliases=True,
            )
        )
        emit_event(
            EVENT_READ_FILTERED,
            tenant_id=tenant,
            model_class=entity.__qualname__,
        )


def register_write_enforcement(cls: type) -> None:
    """Register write-path event listeners on a tenant-aware model class.

    Invoked by the ``@tenant_aware`` decorator at class-definition time
    to attach event listeners for INSERT, UPDATE, and DELETE
    enforcement. Completes DR-021 write enforcement materialization
    in Tarea 3A.4.

    Args:
        cls: SQLAlchemy declarative model class marked as tenant-aware.
    """
    event.listen(cls, "before_insert", _before_insert_handler)
    event.listen(cls, "before_update", _before_update_handler)
    event.listen(cls, "before_delete", _before_delete_handler)


# Session-level read enforcement registration: happens once at module
# import time. Discovers tenant-aware models dynamically per-query via
# the sentinel attribute. DR-022 materialization (Tarea 3A.5).
event.listen(Session, "do_orm_execute", _do_orm_execute_handler)
