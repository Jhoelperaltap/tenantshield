"""SQLAlchemy models for TenantShield Flask example.

Schema shared across all SA adapter examples (FastAPI, Flask, CLI)
per Sub-fase 3C cross-example consistency. Each example carries its
own copy (pedagogical self-containment, NOT shared import).
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tenantshield.adapters.sqlalchemy import tenant_aware


class Base(DeclarativeBase):
    """Declarative base for example models."""


@tenant_aware
class Invoice(Base):
    """Multi-tenant invoice model.

    Decorated with ``@tenant_aware`` to enable TenantShield enforcement:

    - INSERT auto-injects ``tenant_id`` from active scope.
    - UPDATE/DELETE rejects cross-tenant operations.
    - SELECT filters by active tenant scope (read enforcement).
    """

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()
    amount: Mapped[int] = mapped_column()
    description: Mapped[str] = mapped_column()
