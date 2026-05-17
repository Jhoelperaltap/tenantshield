"""Data seeding utility for CLI example.

Inserts demo invoices for acme and globex tenants. Demonstrates
canonical seeding pattern: ``tenant_scope`` + ``bind_tenant`` for
fixture-style data preparation.

The engine + SessionLocal here are module-level so the CLI commands
and tests share the same in-memory database within a single Python
process invocation.
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tenantshield import TenantId, bind_tenant, tenant_scope

from models import Base, Invoice


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)


def seed_demo_data() -> None:
    """Insert demo invoices for acme and globex tenants.

    Canonical seeding pattern: wrap each tenant's inserts in
    ``tenant_scope`` to trigger automatic ``tenant_id`` injection.

    Idempotent: truncates the ``invoices`` table first so repeated
    invocations within the same Python process (e.g., across pytest
    tests sharing the module-level engine) produce a consistent
    fixture set. Truncate uses raw SQL to bypass the read filter
    (per Rule 51: bulk operations are verified via raw SQL).
    """
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM invoices"))

    with tenant_scope(bind_tenant(TenantId("acme"))):
        with SessionLocal() as session:
            session.add(Invoice(amount=100, description="Acme invoice 1"))
            session.add(Invoice(amount=200, description="Acme invoice 2"))
            session.add(Invoice(amount=300, description="Acme invoice 3"))
            session.commit()

    with tenant_scope(bind_tenant(TenantId("globex"))):
        with SessionLocal() as session:
            session.add(Invoice(amount=999, description="Globex invoice 1"))
            session.add(Invoice(amount=1500, description="Globex invoice 2"))
            session.commit()
