"""Unit tests for SQLAlchemy adapter lifecycle module (SessionScope).

Tests SessionScope context manager:

- Direct tenant binding (str + TenantId).
- Callable resolver pattern.
- Fall-through behavior (None tenant / None resolver).
- Mutual exclusivity validation.
- Exception propagation + scope cleanup.
- Nested SessionScope.
- Composition with SA Session operations.

Decision 3 revised per BLOCKER #30: callable-only resolver pattern.
No Phase 2B strategy reuse tested here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tenantshield import TenantId, try_current_tenant
from tenantshield.adapters.sqlalchemy import SessionScope, tenant_aware

if TYPE_CHECKING:
    from collections.abc import Generator


class _Base(DeclarativeBase):
    """Test-local declarative base."""


@tenant_aware
class _Invoice(_Base):
    __tablename__ = "test_invoice_session_scope"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()
    amount: Mapped[int] = mapped_column()


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:")
    _Base.metadata.create_all(engine)
    try:
        with Session(engine) as s:
            yield s
    finally:
        engine.dispose()


class TestSessionScopeDirectBinding:
    """Verify SessionScope with direct tenant parameter."""

    def test_str_tenant_normalized_to_tenant_id(self) -> None:
        """str tenant arg normalized internally to TenantId."""
        with SessionScope(tenant="acme"):
            ctx = try_current_tenant()
            assert ctx is not None
            assert str(ctx.tenant_id) == "acme"

    def test_tenant_id_object_accepted(self) -> None:
        """TenantId arg accepted directly."""
        with SessionScope(tenant=TenantId("acme")):
            ctx = try_current_tenant()
            assert ctx is not None
            assert str(ctx.tenant_id) == "acme"

    def test_scope_cleaned_up_after_block(self) -> None:
        """ContextVar released after block exit."""
        with SessionScope(tenant="acme"):
            assert try_current_tenant() is not None
        assert try_current_tenant() is None

    def test_session_operations_within_scope(self, session: Session) -> None:
        """SA operations within scope receive tenant auto-inject."""
        with SessionScope(tenant="acme"):
            inv = _Invoice(amount=100)
            session.add(inv)
            session.commit()
            assert inv.tenant_id == "acme"


class TestSessionScopeCallableResolver:
    """Verify SessionScope with callable resolver pattern."""

    def test_resolver_returns_str(self) -> None:
        def from_callable() -> str:
            return "globex"

        with SessionScope(resolve_tenant=from_callable):
            ctx = try_current_tenant()
            assert ctx is not None
            assert str(ctx.tenant_id) == "globex"

    def test_resolver_returns_tenant_id(self) -> None:
        def from_callable() -> TenantId:
            return TenantId("acme")

        with SessionScope(resolve_tenant=from_callable):
            ctx = try_current_tenant()
            assert ctx is not None
            assert str(ctx.tenant_id) == "acme"

    def test_resolver_returns_none_fall_through(self) -> None:
        """Resolver returning None falls through (no scope bound)."""

        def no_tenant() -> None:
            return None

        with SessionScope(resolve_tenant=no_tenant):
            assert try_current_tenant() is None


class TestSessionScopeFallThrough:
    """Verify fall-through behavior (no scope bound)."""

    def test_no_tenant_no_resolver_falls_through(self) -> None:
        """No arguments: fall-through, no scope bound."""
        with SessionScope():
            assert try_current_tenant() is None

    def test_tenant_none_explicit_falls_through(self) -> None:
        """Explicit tenant=None: fall-through."""
        with SessionScope(tenant=None):
            assert try_current_tenant() is None


class TestSessionScopeMutualExclusivity:
    """Verify mutual exclusivity of tenant + resolve_tenant."""

    def test_both_raises_value_error(self) -> None:
        def res() -> str:
            return "acme"

        with (
            pytest.raises(ValueError, match="either 'tenant' or 'resolve_tenant'"),
            SessionScope(tenant="acme", resolve_tenant=res),
        ):
            pass


class TestSessionScopeExceptionPropagation:
    """Verify exception propagation through SessionScope."""

    def test_exception_inside_propagates_and_cleans_scope(self) -> None:
        """Exception inside block propagates; scope released."""
        with (  # noqa: PT012
            pytest.raises(ValueError, match="simulated"),
            SessionScope(tenant="acme"),
        ):
            assert try_current_tenant() is not None
            msg = "simulated business rule"
            raise ValueError(msg)

        assert try_current_tenant() is None

    def test_nested_scopes_exception_cleans_all(self) -> None:
        """Exception in inner scope releases both inner + outer."""
        with (  # noqa: PT012
            pytest.raises(RuntimeError, match="inner"),
            SessionScope(tenant="outer"),
            SessionScope(tenant="inner"),
        ):
            msg = "inner fail"
            raise RuntimeError(msg)

        assert try_current_tenant() is None


class TestSessionScopeNesting:
    """Verify nested SessionScope semantics."""

    def test_nested_scopes_inner_overrides(self) -> None:
        """Inner scope overrides outer; outer restored on inner exit."""
        with SessionScope(tenant="outer"):
            outer_ctx = try_current_tenant()
            assert outer_ctx is not None
            assert str(outer_ctx.tenant_id) == "outer"

            with SessionScope(tenant="inner"):
                inner_ctx = try_current_tenant()
                assert inner_ctx is not None
                assert str(inner_ctx.tenant_id) == "inner"

            restored = try_current_tenant()
            assert restored is not None
            assert str(restored.tenant_id) == "outer"
