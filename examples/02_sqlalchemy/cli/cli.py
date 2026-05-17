"""CLI demo for TenantShield SQLAlchemy adapter.

Demonstrates framework-agnostic usage of ``SessionScope`` and
``bind_session_to_tenant`` for batch operations.

Commands:

- ``seed``: insert demo data.
- ``report --tenant <name>``: report invoices for one tenant.
- ``sweep``: iterate known tenants, report each.
- ``nested``: demonstrate nested binding composition.

Run::

    python cli.py <command>

Test::

    pytest tests/
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from tenantshield.adapters.sqlalchemy import (
    SessionScope,
    bind_session_to_tenant,
)

from models import Invoice
from seed import SessionLocal, seed_demo_data


# Known tenants for the sweep command. In production, this would come
# from a tenant registry table or external config.
KNOWN_TENANTS = ("acme", "globex")


def cmd_seed(_args: argparse.Namespace) -> int:
    """Seed demo data."""
    seed_demo_data()
    print("Seeded demo data for tenants:", ", ".join(KNOWN_TENANTS))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Report invoices for a single tenant using ``SessionScope``."""
    tenant = args.tenant

    # SessionScope: declarative tenant context for a code block.
    # Enforcement applies automatically inside the with-block.
    with SessionScope(tenant=tenant), SessionLocal() as session:
        rows = session.execute(select(Invoice)).scalars().all()

        if not rows:
            print(f"Tenant {tenant}: no invoices.")
            return 0

        print(f"Tenant {tenant}: {len(rows)} invoice(s).")
        total = 0
        for r in rows:
            print(f"  id={r.id} amount={r.amount} ({r.description})")
            total += r.amount
        print(f"  Total: {total}")

    return 0


def cmd_sweep(_args: argparse.Namespace) -> int:
    """Sweep all known tenants, report per tenant.

    Demonstrates canonical batch-job pattern: iterate tenants, rebind
    scope per tenant via ``SessionScope``. Tenant scope is independent
    between iterations; no leakage between tenants.
    """
    print("Batch sweep across tenants:")
    print()

    for tenant in KNOWN_TENANTS:
        with SessionScope(tenant=tenant), SessionLocal() as session:
            rows = session.execute(select(Invoice)).scalars().all()
            total = sum(r.amount for r in rows)
            print(f"  Tenant {tenant}: {len(rows)} invoice(s), total={total}")

    print()
    print("Sweep complete.")
    return 0


def cmd_nested(_args: argparse.Namespace) -> int:
    """Demonstrate nested binding (composition pattern).

    Outer ``SessionScope`` + inner ``bind_session_to_tenant`` override.
    Inner exits restore outer (per Sub-fase 3B Tarea 3B.2 composition
    empirical pattern).
    """
    print("Nested binding demo:")
    print()

    with SessionScope(tenant="acme"):
        with SessionLocal() as session:
            outer = session.execute(select(Invoice)).scalars().all()
            print(f"  Outer scope (acme): {len(outer)} invoices")

        with bind_session_to_tenant("globex"), SessionLocal() as inner_session:
            inner = inner_session.execute(select(Invoice)).scalars().all()
            print(f"  Inner scope (globex override): {len(inner)} invoices")

        with SessionLocal() as session_after:
            after = session_after.execute(select(Invoice)).scalars().all()
            print(f"  Outer restored (acme): {len(after)} invoices")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="TenantShield SQLAlchemy CLI example.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("seed", help="Insert demo data.")

    report_parser = subparsers.add_parser(
        "report", help="Report invoices for one tenant.",
    )
    report_parser.add_argument("--tenant", required=True, help="Tenant name.")

    subparsers.add_parser(
        "sweep", help="Iterate all known tenants, report each.",
    )

    subparsers.add_parser(
        "nested",
        help="Demonstrate nested binding (SessionScope + bind_session_to_tenant).",
    )

    args = parser.parse_args(argv)

    # Seed before any non-seed command. In-memory DB resets per
    # Python process; this guarantees data presence for demo commands.
    if args.command != "seed":
        seed_demo_data()

    dispatch = {
        "seed": cmd_seed,
        "report": cmd_report,
        "sweep": cmd_sweep,
        "nested": cmd_nested,
    }

    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
