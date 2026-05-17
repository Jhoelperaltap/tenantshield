"""Unit tests for SQLAlchemy adapter async lifecycle module.

Tests both async helpers:

- ``AsyncSessionScope``: callable resolver + fall-through semantics.
- ``bind_async_session_to_tenant``: direct binding, no fall-through.

Topics covered:

- Direct tenant binding (str + TenantId).
- Callable resolver pattern (AsyncSessionScope only).
- Fall-through behavior (AsyncSessionScope only).
- Mutual exclusivity validation (AsyncSessionScope only).
- Exception propagation + scope cleanup.
- Nested scopes (LIFO restoration).
- Composition between AsyncSessionScope and bind_async_session_to_tenant.

Integration with SA ``AsyncSession`` is covered in Tareas 4A.3, 4A.4,
and 4A.7 (using aiosqlite formally added at Tarea 4A.6); unit tests
here focus on the ContextVar lifecycle wrapping itself, independent
of SA infrastructure. Pattern paralelo to ``test_sqlalchemy_lifecycle``
(Phase 3B precedent for sync ``SessionScope`` + ``bind_session_to_tenant``).
"""

from __future__ import annotations

import pytest

from tenantshield import TenantId, try_current_tenant
from tenantshield.adapters.sqlalchemy import (
    AsyncSessionScope,
    bind_async_session_to_tenant,
)


class TestAsyncSessionScopeDirectBinding:
    """Verify AsyncSessionScope with direct tenant parameter."""

    @pytest.mark.asyncio
    async def test_str_tenant_normalized_to_tenant_id(self) -> None:
        """str tenant arg normalized internally to TenantId."""
        async with AsyncSessionScope(tenant="acme"):
            ctx = try_current_tenant()
            assert ctx is not None
            assert str(ctx.tenant_id) == "acme"

    @pytest.mark.asyncio
    async def test_tenant_id_object_accepted(self) -> None:
        """TenantId arg accepted directly."""
        async with AsyncSessionScope(tenant=TenantId("acme")):
            ctx = try_current_tenant()
            assert ctx is not None
            assert str(ctx.tenant_id) == "acme"

    @pytest.mark.asyncio
    async def test_scope_cleaned_up_after_block(self) -> None:
        """ContextVar released after block exit."""
        async with AsyncSessionScope(tenant="acme"):
            assert try_current_tenant() is not None
        assert try_current_tenant() is None


class TestAsyncSessionScopeCallableResolver:
    """Verify AsyncSessionScope with callable resolver pattern."""

    @pytest.mark.asyncio
    async def test_resolver_returns_str(self) -> None:
        def from_callable() -> str:
            return "globex"

        async with AsyncSessionScope(resolve_tenant=from_callable):
            ctx = try_current_tenant()
            assert ctx is not None
            assert str(ctx.tenant_id) == "globex"

    @pytest.mark.asyncio
    async def test_resolver_returns_tenant_id(self) -> None:
        def from_callable() -> TenantId:
            return TenantId("acme")

        async with AsyncSessionScope(resolve_tenant=from_callable):
            ctx = try_current_tenant()
            assert ctx is not None
            assert str(ctx.tenant_id) == "acme"

    @pytest.mark.asyncio
    async def test_resolver_returns_none_fall_through(self) -> None:
        """Resolver returning None falls through (no scope bound)."""

        def no_tenant() -> None:
            return None

        async with AsyncSessionScope(resolve_tenant=no_tenant):
            assert try_current_tenant() is None


class TestAsyncSessionScopeFallThrough:
    """Verify fall-through behavior (no scope bound)."""

    @pytest.mark.asyncio
    async def test_no_tenant_no_resolver_falls_through(self) -> None:
        """No arguments: fall-through, no scope bound."""
        async with AsyncSessionScope():
            assert try_current_tenant() is None

    @pytest.mark.asyncio
    async def test_tenant_none_explicit_falls_through(self) -> None:
        """Explicit tenant=None: fall-through."""
        async with AsyncSessionScope(tenant=None):
            assert try_current_tenant() is None


class TestAsyncSessionScopeMutualExclusivity:
    """Verify mutual exclusivity of tenant + resolve_tenant."""

    @pytest.mark.asyncio
    async def test_both_raises_value_error(self) -> None:
        def res() -> str:
            return "acme"

        with pytest.raises(ValueError, match="either 'tenant' or 'resolve_tenant'"):
            async with AsyncSessionScope(tenant="acme", resolve_tenant=res):
                pass


class TestAsyncSessionScopeExceptionPropagation:
    """Verify exception propagation through AsyncSessionScope."""

    @pytest.mark.asyncio
    async def test_exception_inside_propagates_and_cleans_scope(self) -> None:
        """Exception inside block propagates; scope released."""
        with pytest.raises(ValueError, match="simulated"):  # noqa: PT012
            async with AsyncSessionScope(tenant="acme"):
                assert try_current_tenant() is not None
                msg = "simulated business rule"
                raise ValueError(msg)

        assert try_current_tenant() is None

    @pytest.mark.asyncio
    async def test_nested_scopes_exception_cleans_all(self) -> None:
        """Exception in inner scope releases both inner + outer."""
        with pytest.raises(RuntimeError, match="inner"):  # noqa: PT012
            async with AsyncSessionScope(tenant="outer"):
                async with AsyncSessionScope(tenant="inner"):
                    msg = "inner fail"
                    raise RuntimeError(msg)

        assert try_current_tenant() is None


class TestAsyncSessionScopeNesting:
    """Verify nested AsyncSessionScope semantics."""

    @pytest.mark.asyncio
    async def test_nested_scopes_inner_overrides(self) -> None:
        """Inner scope overrides outer; outer restored on inner exit."""
        async with AsyncSessionScope(tenant="outer"):
            outer_ctx = try_current_tenant()
            assert outer_ctx is not None
            assert str(outer_ctx.tenant_id) == "outer"

            async with AsyncSessionScope(tenant="inner"):
                inner_ctx = try_current_tenant()
                assert inner_ctx is not None
                assert str(inner_ctx.tenant_id) == "inner"

            restored = try_current_tenant()
            assert restored is not None
            assert str(restored.tenant_id) == "outer"


class TestBindAsyncSessionToTenantDirect:
    """Verify bind_async_session_to_tenant with direct tenant argument."""

    @pytest.mark.asyncio
    async def test_str_tenant_binds_correctly(self) -> None:
        async with bind_async_session_to_tenant("acme"):
            ctx = try_current_tenant()
            assert ctx is not None
            assert str(ctx.tenant_id) == "acme"

    @pytest.mark.asyncio
    async def test_tenant_id_object_accepted(self) -> None:
        async with bind_async_session_to_tenant(TenantId("globex")):
            ctx = try_current_tenant()
            assert ctx is not None
            assert str(ctx.tenant_id) == "globex"

    @pytest.mark.asyncio
    async def test_scope_cleaned_up_after_block(self) -> None:
        async with bind_async_session_to_tenant("acme"):
            assert try_current_tenant() is not None
        assert try_current_tenant() is None

    @pytest.mark.asyncio
    async def test_none_tenant_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty tenant"):
            async with bind_async_session_to_tenant(None):
                pass

    @pytest.mark.asyncio
    async def test_empty_string_tenant_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-empty tenant"):
            async with bind_async_session_to_tenant(""):
                pass


class TestBindAsyncSessionToTenantComposition:
    """Verify bind_async_session_to_tenant composes with AsyncSessionScope."""

    @pytest.mark.asyncio
    async def test_nested_inside_async_session_scope_inner_overrides(self) -> None:
        async with AsyncSessionScope(tenant="outer"):
            async with bind_async_session_to_tenant("inner"):
                inner_ctx = try_current_tenant()
                assert inner_ctx is not None
                assert str(inner_ctx.tenant_id) == "inner"

            outer_ctx = try_current_tenant()
            assert outer_ctx is not None
            assert str(outer_ctx.tenant_id) == "outer"

    @pytest.mark.asyncio
    async def test_exception_inside_bind_cleans_scope(self) -> None:
        with pytest.raises(ValueError, match="simulated"):  # noqa: PT012
            async with bind_async_session_to_tenant("acme"):
                msg = "simulated"
                raise ValueError(msg)

        assert try_current_tenant() is None
