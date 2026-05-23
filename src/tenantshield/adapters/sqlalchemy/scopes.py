"""Ergonomic scope shortcuts for the SQLAlchemy adapter.

Per D-AUDIT-SA-PARITY (2026-05-23) Category 3 gap: the Django adapter
ships ``tenant_scope_for_company(company)`` as a one-line shortcut
over ``tenant_scope(bind_tenant(TenantId(str(company.id))))``. The SA
adapter previously had no equivalent; adopters were required to
write the full incantation at every call site, or to use
``bind_session_to_tenant(tenant_id)`` which is a Session-binding
helper, not a tenant-scope helper.

This module provides ``tenant_scope_for_model(instance)`` as the SA
parity surface. It accepts any SA mapped instance with an ``id``
attribute (typically a tenant entity such as ``Company`` /
``Organization`` / ``Tenant``), reads ``instance.id``, and enters
``tenant_scope`` via the core API.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from tenantshield import bind_tenant, tenant_scope
from tenantshield._types import TenantId

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def tenant_scope_for_model(instance: object) -> Generator[None, None, None]:
    """Enter ``tenant_scope`` derived from an SA mapped instance's ``id``.

    Reads ``instance.id`` and wraps it in ``TenantId(str(...))`` before
    activating the core ``tenant_scope`` context manager. The active
    tenant context is available via ``current_tenant()`` /
    ``try_current_tenant()`` during the block.

    SA parity surface for Django's ``tenant_scope_for_company`` (D-DX.0).
    Catalogued via D-AUDIT-SA-PARITY (2026-05-23) Category 3 hotfix.

    Args:
        instance: Any object with an ``id`` attribute (typically an SA
            mapped instance representing the tenant entity). The value
            of ``instance.id`` is converted to a string and used as the
            tenant identifier.

    Yields:
        ``None``. The active tenant context is bound for the duration
        of the ``with`` block.

    Raises:
        ValueError: If ``instance`` is ``None`` or has no ``id``
            attribute.

    Example:
        >>> from tenantshield.adapters.sqlalchemy import tenant_scope_for_model
        >>> with tenant_scope_for_model(company):
        ...     session.query(Invoice).all()
    """
    if instance is None:
        msg = "tenant_scope_for_model requires a non-None instance."
        raise ValueError(msg)
    tenant_id_raw = getattr(instance, "id", None)
    if tenant_id_raw is None:
        msg = (
            "tenant_scope_for_model requires an instance with an 'id' "
            f"attribute; got {type(instance).__name__} without one."
        )
        raise ValueError(msg)
    with tenant_scope(bind_tenant(TenantId(str(tenant_id_raw)))):
        yield
