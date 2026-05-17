"""End-to-end tests for CLI + TenantShield example.

Validates framework-agnostic ``SessionScope`` + ``bind_session_to_tenant``
usage. Tests via direct ``main()`` invocation; ``capsys`` captures stdout.

Each test invokes ``main()`` independently. ``main()`` auto-seeds before
non-seed commands; seed is idempotent within a single process invocation
since the in-memory database is shared via ``StaticPool``.
"""

from __future__ import annotations

from cli import main


class TestCLIReport:
    """Verify ``report --tenant <name>`` command."""

    def test_report_acme_returns_acme_invoices_only(self, capsys) -> None:
        rc = main(["report", "--tenant", "acme"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Tenant acme: 3 invoice(s)" in captured.out
        assert "Total: 600" in captured.out  # 100+200+300

    def test_report_globex_returns_globex_invoices_only(self, capsys) -> None:
        rc = main(["report", "--tenant", "globex"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Tenant globex: 2 invoice(s)" in captured.out
        assert "Total: 2499" in captured.out  # 999+1500


class TestCLISweep:
    """Verify ``sweep`` command iterates all tenants."""

    def test_sweep_reports_both_tenants(self, capsys) -> None:
        rc = main(["sweep"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Tenant acme: 3 invoice(s)" in captured.out
        assert "Tenant globex: 2 invoice(s)" in captured.out
        assert "Sweep complete." in captured.out


class TestCLINested:
    """Verify nested binding composition (``SessionScope`` + ``bind_session_to_tenant``)."""

    def test_nested_demonstrates_override_and_restoration(self, capsys) -> None:
        rc = main(["nested"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Outer scope (acme): 3 invoices" in captured.out
        assert "Inner scope (globex override): 2 invoices" in captured.out
        assert "Outer restored (acme): 3 invoices" in captured.out


class TestCLISeed:
    """Verify ``seed`` command completes cleanly."""

    def test_seed_completes_without_error(self, capsys) -> None:
        rc = main(["seed"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Seeded demo data" in captured.out
