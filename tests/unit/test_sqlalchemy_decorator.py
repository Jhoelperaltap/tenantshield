"""Unit tests for the SQLAlchemy adapter tenant_aware decorator."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tenantshield.adapters.sqlalchemy import tenant_aware
from tenantshield.exceptions import ConfigurationError


class _Base(DeclarativeBase):
    """Test-local declarative base."""


class TestTenantAwareDecorator:
    """Verify decorator behavior on SA declarative models."""

    def test_decorates_valid_model_returns_same_class(self) -> None:
        @tenant_aware
        class Invoice(_Base):
            __tablename__ = "test_invoice_valid"
            id: Mapped[int] = mapped_column(primary_key=True)
            tenant_id: Mapped[str] = mapped_column()

        assert hasattr(Invoice, "__tenantshield_tenant_aware__")
        assert Invoice.__tenantshield_tenant_aware__ is True

    def test_missing_tenant_id_column_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError) as exc_info:

            @tenant_aware
            class Broken(_Base):
                __tablename__ = "test_broken_no_tenant_id"
                id: Mapped[int] = mapped_column(primary_key=True)

        assert "tenant_id" in str(exc_info.value)
        assert "Broken" in str(exc_info.value)

    def test_configuration_error_message_includes_remediation_hint(self) -> None:
        with pytest.raises(ConfigurationError) as exc_info:

            @tenant_aware
            class NoTenant(_Base):
                __tablename__ = "test_no_tenant_remediation"
                id: Mapped[int] = mapped_column(primary_key=True)

        assert "Mapped[str]" in str(exc_info.value)

    def test_tenant_id_can_be_non_string_type(self) -> None:
        @tenant_aware
        class IntTenantModel(_Base):
            __tablename__ = "test_int_tenant"
            id: Mapped[int] = mapped_column(primary_key=True)
            tenant_id: Mapped[int] = mapped_column()

        assert IntTenantModel.__tenantshield_tenant_aware__ is True

    def test_class_without_table_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError) as exc_info:

            @tenant_aware
            class NotADeclarativeModel:  # type: ignore[misc, type-var]
                pass

        msg = str(exc_info.value)
        assert "__table__" in msg or "DeclarativeBase" in msg

    def test_decorator_preserves_other_attributes(self) -> None:
        @tenant_aware
        class WithOtherAttrs(_Base):
            __tablename__ = "test_other_attrs"
            id: Mapped[int] = mapped_column(primary_key=True)
            tenant_id: Mapped[str] = mapped_column()
            amount: Mapped[int] = mapped_column()
            description: Mapped[str] = mapped_column()

        assert "amount" in WithOtherAttrs.__table__.columns
        assert "description" in WithOtherAttrs.__table__.columns
        assert WithOtherAttrs.__tenantshield_tenant_aware__ is True

    def test_decorator_can_be_applied_to_multiple_models(self) -> None:
        @tenant_aware
        class ModelA(_Base):
            __tablename__ = "test_model_a"
            id: Mapped[int] = mapped_column(primary_key=True)
            tenant_id: Mapped[str] = mapped_column()

        @tenant_aware
        class ModelB(_Base):
            __tablename__ = "test_model_b"
            id: Mapped[int] = mapped_column(primary_key=True)
            tenant_id: Mapped[str] = mapped_column()

        assert ModelA.__tenantshield_tenant_aware__ is True
        assert ModelB.__tenantshield_tenant_aware__ is True
        assert ModelA is not ModelB
