"""Tenant-aware decorator for SQLAlchemy declarative models.

The ``@tenant_aware`` decorator applies multi-tenant enforcement to
SQLAlchemy declarative model classes. Decoration:

1. Validates that the model declares a ``tenant_id: Mapped[str]`` column.
2. Registers event listeners for write enforcement.
3. Registers session-level event for read filtering.

Implementation of the decorator body is materialized in Tarea 3A.2.
This module exists as scaffolding only at this stage of Sub-fase 3A.
"""

from __future__ import annotations


def tenant_aware(cls: type) -> type:
    """Mark a SQLAlchemy declarative model as tenant-aware.

    Not yet implemented (scaffolding only, Tarea 3A.1 of Sub-fase 3A).
    Body materialized in Tarea 3A.2.

    Raises:
        NotImplementedError: always, until Tarea 3A.2 materializes the
            decorator body.
    """
    msg = "tenant_aware decorator scaffolding only; implementation in 3A.2"
    raise NotImplementedError(msg)
