"""Flask + TenantShield SQLAlchemy adapter example.

Demonstrates:

- WSGI middleware integration (``TenantSessionMiddlewareWSGI``).
- Callable resolver pattern for tenant extraction (header-based).
- WSGI generator pattern (Rule 54) preserves scope during response iteration.
- Strict mode opt-in (``on_missing_tenant='raise'``) via separate
  ``strict_app`` factory.

Run::

    flask --app app run

Test::

    pytest tests/

WSGI environ header format: ``HTTP_<UPPERCASE_NAME>`` string keys.
Header ``X-Tenant-ID`` -> environ key ``HTTP_X_TENANT_ID``.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, jsonify
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tenantshield import TenantId, bind_tenant, tenant_scope
from tenantshield.adapters.sqlalchemy import TenantSessionMiddlewareWSGI

from models import Base, Invoice


# Database setup. StaticPool + check_same_thread=False required for
# in-memory SQLite with Flask test client's threaded request handling.
# Real adopters with file-backed SQLite or PostgreSQL/MySQL omit pool config.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)


def _seed_data() -> None:
    """Insert demo data for acme and globex tenants."""
    with tenant_scope(bind_tenant(TenantId("acme"))):
        with SessionLocal() as session:
            session.add(Invoice(amount=100, description="Acme invoice 1"))
            session.add(Invoice(amount=200, description="Acme invoice 2"))
            session.commit()

    with tenant_scope(bind_tenant(TenantId("globex"))):
        with SessionLocal() as session:
            session.add(Invoice(amount=999, description="Globex invoice 1"))
            session.commit()


_seed_data()


def resolve_tenant_from_environ(environ: dict[str, Any]) -> str | None:
    """Extract ``X-Tenant-ID`` header from WSGI environ.

    WSGI environ headers are encoded as ``HTTP_<UPPERCASE_NAME>`` string
    keys per PEP 3333. ``X-Tenant-ID`` -> ``HTTP_X_TENANT_ID``.

    Canonical callable resolver pattern per Sub-fase 3B BLOCKER #30
    resolution: Phase 2B strategy classes are Django-bound (use
    ``request.META`` / ``request.get_host()``), NOT reusable here.
    """
    return environ.get("HTTP_X_TENANT_ID")


def create_app() -> Flask:
    """Application factory.

    Wraps Flask's ``wsgi_app`` with ``TenantSessionMiddlewareWSGI``
    for tenant context binding per request.
    """
    flask_app = Flask(__name__)

    @flask_app.route("/invoices")
    def get_invoices() -> Any:
        with SessionLocal() as session:
            rows = session.execute(select(Invoice)).scalars().all()
            return jsonify(
                [
                    {
                        "id": r.id,
                        "tenant_id": r.tenant_id,
                        "amount": r.amount,
                        "description": r.description,
                    }
                    for r in rows
                ]
            )

    flask_app.wsgi_app = TenantSessionMiddlewareWSGI(  # type: ignore[method-assign]
        flask_app.wsgi_app,
        resolve_tenant=resolve_tenant_from_environ,
    )

    return flask_app


def create_strict_app() -> Flask:
    """Application factory with strict mode enforcement (DR-026).

    Middleware configured with ``on_missing_tenant='raise'`` triggers
    ``MissingTenantContextError`` when ``resolve_tenant`` returns ``None``.
    """
    flask_app = Flask(__name__)

    @flask_app.route("/invoices")
    def get_invoices_strict() -> Any:
        with SessionLocal() as session:
            rows = session.execute(select(Invoice)).scalars().all()
            return jsonify(
                [{"id": r.id, "tenant_id": r.tenant_id} for r in rows]
            )

    flask_app.wsgi_app = TenantSessionMiddlewareWSGI(  # type: ignore[method-assign]
        flask_app.wsgi_app,
        resolve_tenant=resolve_tenant_from_environ,
        on_missing_tenant="raise",
    )

    return flask_app


# Module-level instances for `flask --app app run` and tests.
app = create_app()
strict_app = create_strict_app()
