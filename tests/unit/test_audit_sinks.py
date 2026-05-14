"""Tests for tenantshield.audit built-in sinks."""

from __future__ import annotations

import structlog
from structlog.testing import capture_logs

from tenantshield import TenantContext, TenantId
from tenantshield.audit import (
    AuditEvent,
    AuditEventType,
    AuditSink,
    InMemorySink,
    NullSink,
    StructLogSink,
)


def test_null_sink_discards() -> None:
    """NullSink does not raise and has no observable state."""
    sink = NullSink()
    for _ in range(100):
        sink.emit(AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None))


def test_in_memory_sink_accumulates() -> None:
    sink = InMemorySink()
    events = [
        AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None),
        AuditEvent(event_type=AuditEventType.POLICY_ALLOW, tenant_context=None),
        AuditEvent(event_type=AuditEventType.POLICY_DENY, tenant_context=None),
    ]
    for e in events:
        sink.emit(e)
    assert sink.events == events


def test_in_memory_sink_clear() -> None:
    sink = InMemorySink()
    sink.emit(AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None))
    assert len(sink.events) == 1
    sink.clear()
    assert sink.events == []


def test_in_memory_sink_isinstance_audit_sink() -> None:
    assert isinstance(InMemorySink(), AuditSink)


def test_struct_log_sink_default_logger() -> None:
    """Instantiating without an argument uses a default structlog logger."""
    sink = StructLogSink()
    with capture_logs() as captured:
        sink.emit(AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None))
    assert len(captured) == 1


def test_struct_log_sink_custom_logger() -> None:
    """Instantiating with a custom logger uses it for emit."""
    custom = structlog.get_logger("test.custom")
    sink = StructLogSink(logger=custom)
    with capture_logs() as captured:
        sink.emit(AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None))
    assert len(captured) == 1


def test_struct_log_sink_event_fields() -> None:
    """Captured log has the expected structured fields, with tenant_id set."""
    ctx = TenantContext(tenant_id=TenantId("acme"))
    sink = StructLogSink()
    event = AuditEvent(
        event_type=AuditEventType.POLICY_ALLOW,
        tenant_context=ctx,
        payload={"reason": "demo"},
    )

    with capture_logs() as captured:
        sink.emit(event)

    assert len(captured) == 1
    log_entry = captured[0]
    assert log_entry["event"] == "policy_allow"
    assert log_entry["log_level"] == "info"
    assert "timestamp" in log_entry
    assert log_entry["tenant_id"] == "acme"
    assert log_entry["payload"] == {"reason": "demo"}


def test_struct_log_sink_with_none_context() -> None:
    """tenant_id field is None when no context is active."""
    sink = StructLogSink()
    event = AuditEvent(
        event_type=AuditEventType.SINK_FAILURE,
        tenant_context=None,
    )

    with capture_logs() as captured:
        sink.emit(event)

    assert captured[0]["tenant_id"] is None
