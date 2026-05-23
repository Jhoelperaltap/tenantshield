"""Tests for SA migration metadata helpers (D-HOTFIX-v061, SA Cat 3 parity)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tenantshield.adapters.sqlalchemy import (
    TenantAwareModelMetadata,
    get_model_metadata,
    tenant_aware,
    tenant_aware_models,
)


class _Base(DeclarativeBase):
    """Test-scoped DeclarativeBase to keep the registry isolated."""


@tenant_aware
class _BenchInvoice(_Base):
    __tablename__ = "bench_invoice_metadata_test"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()


@tenant_aware
class _BenchPayment(_Base):
    __tablename__ = "bench_payment_metadata_test"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()


class _PlainModel(_Base):
    __tablename__ = "plain_metadata_test"
    id: Mapped[int] = mapped_column(primary_key=True)


def test_tenant_aware_models_yields_registered_entries() -> None:
    """Every decorated class surfaces via the iterator."""
    qualnames = {meta.model_qualname for meta in tenant_aware_models()}
    assert any(q.endswith("_BenchInvoice") for q in qualnames)
    assert any(q.endswith("_BenchPayment") for q in qualnames)


def test_get_model_metadata_for_registered_returns_snapshot() -> None:
    """Lookup returns a frozen dataclass for a registered class."""
    meta = get_model_metadata(_BenchInvoice)
    assert meta is not None
    assert isinstance(meta, TenantAwareModelMetadata)
    assert meta.tenant_field == "tenant_id"
    assert meta.model_qualname.endswith("_BenchInvoice")


def test_get_model_metadata_for_plain_class_returns_none() -> None:
    """Non-tenant-aware classes are signalled by ``None``."""
    assert get_model_metadata(_PlainModel) is None


def test_metadata_auto_propagate_default_false_pre_phase_7() -> None:
    """``auto_propagate_from_parent_fk`` default is ``False`` pre-Phase-7 SA-AUTO.0."""
    meta = get_model_metadata(_BenchInvoice)
    assert meta is not None
    assert meta.auto_propagate_from_parent_fk is False
