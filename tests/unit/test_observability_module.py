"""Unit tests for ``tenantshield.observability`` module scaffolding (Sub-fase 5B.1)."""

from __future__ import annotations

import structlog.testing

from tenantshield import observability
from tenantshield.observability import (
    ALL_EVENTS,
    EVENT_SCOPE_ENTERED,
    EVENT_SEVERITY,
    configure,
    is_enabled,
)
from tenantshield.observability._emit import emit_event


class TestObservabilityConfiguration:
    """Verify ``configure()`` + ``is_enabled()`` behavior."""

    def setup_method(self) -> None:
        configure(emit_events=False)

    def teardown_method(self) -> None:
        configure(emit_events=False)

    def test_disabled_by_default(self) -> None:
        assert is_enabled() is False

    def test_configure_enables(self) -> None:
        configure(emit_events=True)
        assert is_enabled() is True

    def test_configure_disables(self) -> None:
        configure(emit_events=True)
        configure(emit_events=False)
        assert is_enabled() is False


class TestEventTaxonomy:
    """Verify 9-event taxonomy + severity tiering canonical map."""

    def test_event_count(self) -> None:
        assert len(ALL_EVENTS) == 9

    def test_severity_map_complete(self) -> None:
        assert set(EVENT_SEVERITY.keys()) == set(ALL_EVENTS)

    def test_severity_tiering_distribution(self) -> None:
        debug = sum(1 for s in EVENT_SEVERITY.values() if s == "debug")
        info = sum(1 for s in EVENT_SEVERITY.values() if s == "info")
        warning = sum(1 for s in EVENT_SEVERITY.values() if s == "warning")
        assert debug == 5
        assert info == 2
        assert warning == 2

    def test_event_name_namespacing(self) -> None:
        for event in ALL_EVENTS:
            assert event.startswith("tenant.")


class TestEmissionDisabledDefault:
    """Verify disabled-default gate behavior."""

    def setup_method(self) -> None:
        configure(emit_events=False)

    def teardown_method(self) -> None:
        configure(emit_events=False)

    def test_emit_disabled_no_op(self) -> None:
        """Disabled state: ``emit_event`` is no-op (zero captured events)."""
        with structlog.testing.capture_logs() as captured:
            emit_event(EVENT_SCOPE_ENTERED, tenant_id="acme")
        assert len(captured) == 0

    def test_emit_enabled_dispatches(self) -> None:
        """Enabled state: ``emit_event`` invokes logger with event name + fields."""
        configure(emit_events=True)
        with structlog.testing.capture_logs() as captured:
            emit_event(EVENT_SCOPE_ENTERED, tenant_id="acme")
        assert len(captured) == 1
        assert captured[0]["event"] == EVENT_SCOPE_ENTERED
        assert captured[0]["tenant_id"] == "acme"

    def test_emit_uses_severity_map(self) -> None:
        """``emit_event`` dispatches to severity tier per ``EVENT_SEVERITY``."""
        configure(emit_events=True)
        with structlog.testing.capture_logs() as captured:
            emit_event(EVENT_SCOPE_ENTERED, tenant_id="acme")
        assert captured[0]["log_level"] == "info"


class TestModuleSurface:
    """Verify public API surface available at observability namespace."""

    def test_module_importable(self) -> None:
        assert observability is not None

    def test_public_api_present(self) -> None:
        assert hasattr(observability, "configure")
        assert hasattr(observability, "is_enabled")
        assert hasattr(observability, "ALL_EVENTS")
        assert hasattr(observability, "EVENT_SEVERITY")
