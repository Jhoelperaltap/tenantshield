"""Synchronous tenant context management for TenantShield.

This module defines :class:`TenantContext` and the free functions to activate,
inspect, and construct contexts. The active context is stored in a module-level
:class:`contextvars.ContextVar`, which makes it inherently thread- and
asyncio-task-isolated without monkey-patching.

The asynchronous counterpart (``atenant_scope``) is added to this module in
sub-phase 1A.4.
"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tenantshield.exceptions import MissingTenantContextError

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

    from tenantshield._types import TenantId


def _empty_metadata() -> dict[str, object]:
    """Factory for the default empty metadata mapping of TenantContext."""
    return {}


@dataclass(frozen=True, slots=True, kw_only=True)
class TenantContext:
    """A frozen, slotted tenant context.

    Attributes:
        tenant_id: The tenant identifier.
        metadata: Arbitrary metadata associated with this context. Defaults to
            an empty mapping. Although the field is typed as ``Mapping``
            (read-only in spirit), the underlying object may be a mutable
            dict — TenantShield does not enforce immutability of the contents.
            Treat the metadata as immutable from outside the package.
    """

    tenant_id: TenantId
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)


_TENANT_CONTEXT: ContextVar[TenantContext | None] = ContextVar(
    "tenantshield.tenant_context", default=None
)


def _bind_and_token(ctx: TenantContext) -> Token[TenantContext | None]:
    """Bind ``ctx`` to the active context and return the reset token.

    Internal helper shared by sync and async scope context managers to avoid
    duplicating the contextvar set/reset boilerplate.
    """
    return _TENANT_CONTEXT.set(ctx)


@contextlib.contextmanager
def tenant_scope(ctx: TenantContext) -> Generator[TenantContext, None, None]:
    """Activate ``ctx`` as the current tenant for the duration of the block.

    Args:
        ctx: The tenant context to activate.

    Yields:
        The same context, for ergonomic ``with`` binding.

    Example:
        >>> with tenant_scope(bind_tenant(TenantId("acme"))) as ctx:
        ...     assert current_tenant() is ctx
    """
    token = _bind_and_token(ctx)
    try:
        yield ctx
    finally:
        _TENANT_CONTEXT.reset(token)


def current_tenant() -> TenantContext:
    """Return the active tenant context.

    Raises:
        MissingTenantContextError: if no tenant scope is active.
    """
    ctx = _TENANT_CONTEXT.get()
    if ctx is None:
        raise MissingTenantContextError(operation="current_tenant")
    return ctx


def try_current_tenant() -> TenantContext | None:
    """Return the active tenant context, or ``None`` if none is active."""
    return _TENANT_CONTEXT.get()


def bind_tenant(tenant_id: TenantId, /, **metadata: object) -> TenantContext:
    """Construct a :class:`TenantContext` without activating it.

    The ``/`` makes ``tenant_id`` positional-only — callers must write
    ``bind_tenant(TenantId("acme"), region="eu")`` and not
    ``bind_tenant(tenant_id=TenantId("acme"), region="eu")``. This forces
    visual clarity at call sites.

    Args:
        tenant_id: The tenant identifier (positional-only).
        **metadata: Arbitrary metadata keyword arguments attached to the context.

    Returns:
        A new ``TenantContext``. To activate it, wrap with :func:`tenant_scope`.

    Example:
        >>> ctx = bind_tenant(TenantId("acme"), region="eu")
        >>> with tenant_scope(ctx):
        ...     pass
    """
    return TenantContext(tenant_id=tenant_id, metadata=metadata)


__all__ = [
    "TenantContext",
    "bind_tenant",
    "current_tenant",
    "tenant_scope",
    "try_current_tenant",
]
