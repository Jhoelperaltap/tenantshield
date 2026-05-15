"""Tenant-aware decorator for SQLAlchemy declarative models.

The ``@tenant_aware`` decorator applies multi-tenant enforcement to
SQLAlchemy declarative model classes. Decoration:

1. Validates that the model declares a ``tenant_id`` column.
2. Marks the model class as tenant-aware via a sentinel attribute.
3. Registers event listeners for write-time enforcement (deferred to
   Tareas 3A.3-4; this module only marks the class).
4. The session-level ``do_orm_execute`` event listener (Tarea 3A.5)
   will discover tenant-aware models via the sentinel attribute and
   apply read-time filtering.

The decorator validates at class-definition time (fail-fast). If a
class is decorated without a ``tenant_id`` column,
``ConfigurationError`` is raised before the application starts
processing requests.

Usage
-----

.. code-block:: python

    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
    from tenantshield.adapters.sqlalchemy import tenant_aware


    class Base(DeclarativeBase):
        pass


    @tenant_aware
    class Invoice(Base):
        __tablename__ = "invoice"

        id: Mapped[int] = mapped_column(primary_key=True)
        tenant_id: Mapped[str] = mapped_column()
        amount: Mapped[int] = mapped_column()

Architectural notes
-------------------

The decorator only marks the class. Event listener registration is
delayed to the events module (Tareas 3A.3-5) to keep concerns
separated and to allow event listeners to be tested in isolation
from the decorator surface.

The sentinel attribute name ``__tenantshield_tenant_aware__`` is
deliberately namespaced via dunder convention to avoid collision
with adopter-defined class attributes.

See also
--------

- ADR-0006 (SQLAlchemy 2.0+ only).
- ADR-0007 (TBD: event-based enforcement, materialization post-3A.5).
- DR-021/022 (write + read enforcement, materialization in 3A.3-5).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from tenantshield.adapters.sqlalchemy.events import (
    _TENANT_AWARE_SENTINEL,  # pyright: ignore[reportPrivateUsage]  # package-internal constant; sentinel name shared with do_orm_execute handler
    register_write_enforcement,
)
from tenantshield.exceptions import ConfigurationError

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase


_TENANT_ID_COLUMN_NAME = "tenant_id"

T = TypeVar("T", bound="type[DeclarativeBase]")


def tenant_aware(cls: T) -> T:
    """Mark a SQLAlchemy declarative model as tenant-aware.

    Validates that the model has a ``tenant_id`` column and marks the
    class via a sentinel attribute. Event listener registration is
    handled separately (events module).

    Args:
        cls: SQLAlchemy declarative model class to mark as
            tenant-aware. Must declare a ``tenant_id`` column
            (typically ``Mapped[str]``).

    Returns:
        The same class, with ``__tenantshield_tenant_aware__``
        attribute set to ``True``.

    Raises:
        ConfigurationError: If the model class does not declare a
            ``tenant_id`` column, or does not inherit from
            ``DeclarativeBase`` (no ``__table__`` attribute). Raised
            at class-definition time (fail-fast).

    Examples:
        Basic usage::

            @tenant_aware
            class Invoice(Base):
                __tablename__ = "invoice"

                id: Mapped[int] = mapped_column(primary_key=True)
                tenant_id: Mapped[str] = mapped_column()

        Missing ``tenant_id`` column raises at class definition time::

            @tenant_aware
            class BrokenModel(Base):  # raises ConfigurationError
                __tablename__ = "broken"
                id: Mapped[int] = mapped_column(primary_key=True)
    """
    table = getattr(cls, "__table__", None)
    if table is None:
        msg = (
            f"@tenant_aware requires a SQLAlchemy declarative model with "
            f"a mapped table. Class {cls.__name__!r} has no __table__ "
            f"attribute. Ensure the class inherits from DeclarativeBase "
            f"and declares __tablename__."
        )
        raise ConfigurationError(msg)

    if _TENANT_ID_COLUMN_NAME not in table.columns:
        msg = (
            f"@tenant_aware requires class {cls.__name__!r} to declare a "
            f"{_TENANT_ID_COLUMN_NAME!r} column. Add: "
            f"tenant_id: Mapped[str] = mapped_column()"
        )
        raise ConfigurationError(msg)

    setattr(cls, _TENANT_AWARE_SENTINEL, True)

    register_write_enforcement(cls)

    return cls
