"""Unit tests for scope lifecycle events emission (Sub-fase 5B.2).

Verifies ``SessionScope`` + ``AsyncSessionScope`` emit the 3 scope
lifecycle events per Tarea 5B.0 Scenario #1 baseline:

- ``tenant.scope.entered`` (INFO) -- on successful tenant binding.
- ``tenant.scope.exited`` (INFO) -- on successful scope exit.
- ``tenant.scope.exception`` (WARNING) -- on exception inside scope.

Fall-through case (no tenant resolved) emits NO scope events --
preserves the "scope events imply tenant bound" semantic.
"""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from tenantshield.adapters.sqlalchemy import AsyncSessionScope, SessionScope
from tenantshield.observability import configure
from tenantshield.observability.events import (
    EVENT_SCOPE_ENTERED,
    EVENT_SCOPE_EXCEPTION,
    EVENT_SCOPE_EXITED,
)

_SCOPE_EVENTS = (EVENT_SCOPE_ENTERED, EVENT_SCOPE_EXITED, EVENT_SCOPE_EXCEPTION)


@pytest.fixture(autouse=True)
def _reset_observability():
    """Reset observability flag around each test for isolation."""
    configure(emit_events=False)
    yield
    configure(emit_events=False)


def _raise_value_error_inside_session_scope(tenant: str, message: str) -> None:
    """Helper: raise ``ValueError`` inside a ``SessionScope`` block.

    Single-statement helper used inside ``pytest.raises`` to satisfy PT012
    (the with-block does not collapse into ``pytest.raises``).
    """
    with SessionScope(tenant=tenant):
        raise ValueError(message)


async def _raise_value_error_inside_async_session_scope(tenant: str, message: str) -> None:
    """Async helper parallel to :func:`_raise_value_error_inside_session_scope`."""
    async with AsyncSessionScope(tenant=tenant):
        raise ValueError(message)


class TestSessionScopeLifecycleEvents:
    """Verify sync ``SessionScope`` emits scope lifecycle events."""

    def test_scope_entered_emitted_when_enabled(self) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, SessionScope(tenant="acme"):
            pass

        entered = [entry for entry in logs if entry.get("event") == EVENT_SCOPE_ENTERED]
        assert len(entered) == 1
        assert entered[0]["tenant_id"] == "acme"
        assert entered[0]["scope_class"] == "SessionScope"

    def test_scope_exited_emitted_on_success(self) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, SessionScope(tenant="acme"):
            pass

        exited = [entry for entry in logs if entry.get("event") == EVENT_SCOPE_EXITED]
        assert len(exited) == 1
        assert exited[0]["tenant_id"] == "acme"
        assert exited[0]["scope_class"] == "SessionScope"

    def test_no_exception_event_on_success(self) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, SessionScope(tenant="acme"):
            pass

        exception_events = [entry for entry in logs if entry.get("event") == EVENT_SCOPE_EXCEPTION]
        assert len(exception_events) == 0

    def test_scope_exception_emitted_on_exception(self) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, pytest.raises(ValueError, match="test error"):
            _raise_value_error_inside_session_scope("acme", "test error")

        exception_events = [entry for entry in logs if entry.get("event") == EVENT_SCOPE_EXCEPTION]
        assert len(exception_events) == 1
        assert exception_events[0]["exception_type"] == "ValueError"
        assert exception_events[0]["tenant_id"] == "acme"
        assert exception_events[0]["scope_class"] == "SessionScope"

    def test_no_exited_event_on_exception(self) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, pytest.raises(ValueError, match="boom"):
            _raise_value_error_inside_session_scope("acme", "boom")

        exited = [entry for entry in logs if entry.get("event") == EVENT_SCOPE_EXITED]
        assert len(exited) == 0

    def test_no_emission_when_disabled(self) -> None:
        configure(emit_events=False)
        with capture_logs() as logs, SessionScope(tenant="acme"):
            pass

        scope_events = [entry for entry in logs if entry.get("event") in _SCOPE_EVENTS]
        assert len(scope_events) == 0

    def test_no_emission_on_fall_through(self) -> None:
        """No tenant resolved -> no scope events emitted (semantic preservation)."""
        configure(emit_events=True)
        with capture_logs() as logs, SessionScope():
            pass

        scope_events = [entry for entry in logs if entry.get("event") in _SCOPE_EVENTS]
        assert len(scope_events) == 0


class TestAsyncSessionScopeLifecycleEvents:
    """Verify async ``AsyncSessionScope`` emits scope lifecycle events."""

    @pytest.mark.asyncio
    async def test_scope_entered_emitted_when_enabled(self) -> None:
        configure(emit_events=True)
        with capture_logs() as logs:
            async with AsyncSessionScope(tenant="acme"):
                pass

        entered = [entry for entry in logs if entry.get("event") == EVENT_SCOPE_ENTERED]
        assert len(entered) == 1
        assert entered[0]["tenant_id"] == "acme"
        assert entered[0]["scope_class"] == "AsyncSessionScope"

    @pytest.mark.asyncio
    async def test_scope_exited_emitted_on_success(self) -> None:
        configure(emit_events=True)
        with capture_logs() as logs:
            async with AsyncSessionScope(tenant="acme"):
                pass

        exited = [entry for entry in logs if entry.get("event") == EVENT_SCOPE_EXITED]
        assert len(exited) == 1
        assert exited[0]["scope_class"] == "AsyncSessionScope"

    @pytest.mark.asyncio
    async def test_scope_exception_emitted_on_exception(self) -> None:
        configure(emit_events=True)
        with capture_logs() as logs, pytest.raises(ValueError, match="async test"):
            await _raise_value_error_inside_async_session_scope("acme", "async test")

        exception_events = [entry for entry in logs if entry.get("event") == EVENT_SCOPE_EXCEPTION]
        assert len(exception_events) == 1
        assert exception_events[0]["exception_type"] == "ValueError"
        assert exception_events[0]["scope_class"] == "AsyncSessionScope"

    @pytest.mark.asyncio
    async def test_no_emission_on_fall_through_async(self) -> None:
        configure(emit_events=True)
        with capture_logs() as logs:
            async with AsyncSessionScope():
                pass

        scope_events = [entry for entry in logs if entry.get("event") in _SCOPE_EVENTS]
        assert len(scope_events) == 0
