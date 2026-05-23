"""Django ergonomic shortcuts for tenant scope management."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from tenantshield import bind_tenant, tenant_scope
from tenantshield._types import TenantId

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def tenant_scope_for_company(company: object) -> Generator[None, None, None]:
    """Context manager that binds the current tenant from a Django model instance.

    Sugar over the canonical
    ``with tenant_scope(bind_tenant(TenantId(str(company.id)))):``. Reduces
    friction at adopter call sites that already hold a model instance
    (typically the project's ``Company`` / ``Tenant`` / ``Org`` model).

    Per Finding #6 (Counterbook ADR-0015 catalog); resolves the
    ``TenantId(str(...))`` verbosity surfaced in real adopter use.

    Args:
        company: Any object with an ``id`` attribute (typically a Django
            model instance). The value of ``company.id`` is converted to a
            string and used as the tenant identifier.

    Yields:
        ``None``. The active tenant context is available via the standard
        ``current_tenant()`` / ``try_current_tenant()`` accessors during
        the block.

    Raises:
        ValueError: If ``company`` is ``None`` or has no ``id`` attribute.

    Example:
        >>> from tenantshield.adapters.django import tenant_scope_for_company
        >>> with tenant_scope_for_company(request.company):
        ...     Invoice.objects.create(amount=100)
    """
    if company is None:
        msg = "tenant_scope_for_company requires a non-None company instance."
        raise ValueError(msg)
    company_id = getattr(company, "id", None)
    if company_id is None:
        msg = (
            "tenant_scope_for_company requires a company with an 'id' attribute; "
            f"got {type(company).__name__} without one."
        )
        raise ValueError(msg)
    with tenant_scope(bind_tenant(TenantId(str(company_id)))):
        yield
