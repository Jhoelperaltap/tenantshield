"""Integration tests verifying that tenant scopes emit audit events."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tenantshield import TenantId, atenant_scope, bind_tenant, tenant_scope
from tenantshield.audit import (
    _SINKS_REGISTRY,
    AuditEvent,
    AuditEventType,
    register_sink,
)

if TYPE_CHECKING:
    from tenantshield.audit import InMemorySink


def test_tenant_scope_emits_bound_and_released(capture_audit: InMemorySink) -> None:
    ctx = bind_tenant(TenantId("acme"))
    with tenant_scope(ctx):
        pass

    assert len(capture_audit.events) == 2
    assert capture_audit.events[0].event_type == AuditEventType.CONTEXT_BOUND
    assert capture_audit.events[0].tenant_context is ctx
    assert capture_audit.events[1].event_type == AuditEventType.CONTEXT_RELEASED
    assert capture_audit.events[1].tenant_context is ctx


@pytest.mark.asyncio
async def test_atenant_scope_emits_bound_and_released(capture_audit: InMemorySink) -> None:
    ctx = bind_tenant(TenantId("acme"))
    async with atenant_scope(ctx):
        pass

    assert len(capture_audit.events) == 2
    assert capture_audit.events[0].event_type == AuditEventType.CONTEXT_BOUND
    assert capture_audit.events[1].event_type == AuditEventType.CONTEXT_RELEASED


def test_nested_scopes_emit_in_order(capture_audit: InMemorySink) -> None:
    outer = bind_tenant(TenantId("outer"))
    inner = bind_tenant(TenantId("inner"))

    with tenant_scope(outer), tenant_scope(inner):
        pass

    types = [e.event_type for e in capture_audit.events]
    assert types == [
        AuditEventType.CONTEXT_BOUND,
        AuditEventType.CONTEXT_BOUND,
        AuditEventType.CONTEXT_RELEASED,
        AuditEventType.CONTEXT_RELEASED,
    ]


def test_scope_exception_still_emits_released(capture_audit: InMemorySink) -> None:
    ctx = bind_tenant(TenantId("acme"))

    class _BoomError(Exception):
        pass

    with pytest.raises(_BoomError), tenant_scope(ctx):
        raise _BoomError

    assert len(capture_audit.events) == 2
    assert capture_audit.events[1].event_type == AuditEventType.CONTEXT_RELEASED


def test_failing_sink_does_not_break_scope() -> None:
    """A sink that raises does not interrupt the scope."""
    original = list(_SINKS_REGISTRY)
    _SINKS_REGISTRY.clear()

    class _FailingSink:
        def emit(self, _event: AuditEvent) -> None:
            msg = "sink boom"
            raise RuntimeError(msg)

    register_sink(_FailingSink())
    try:
        ctx = bind_tenant(TenantId("acme"))
        # This MUST NOT raise.
        with tenant_scope(ctx) as bound_ctx:
            assert bound_ctx is ctx
    finally:
        _SINKS_REGISTRY.clear()
        for sink in original:
            register_sink(sink)


def test_silent_audit_swallows_events(silent_audit) -> None:  # noqa: ARG001
    """silent_audit fixture results in no observable events."""
    ctx = bind_tenant(TenantId("acme"))
    with tenant_scope(ctx):
        pass
    # No observable assertion possible: NullSink does not retain state.
    # The test passes if no error is raised and the scope completes.
