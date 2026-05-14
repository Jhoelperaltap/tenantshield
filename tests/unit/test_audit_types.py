"""Tests for tenantshield.audit type primitives."""

from __future__ import annotations

import dataclasses
import json
import time
from datetime import UTC, datetime

import pytest

from tenantshield.audit import AuditEvent, AuditEventType, AuditSink


def test_audit_event_type_str_values() -> None:
    assert AuditEventType.CONTEXT_BOUND == "context_bound"
    assert AuditEventType.CONTEXT_RELEASED == "context_released"
    assert AuditEventType.POLICY_ALLOW == "policy_allow"
    assert AuditEventType.POLICY_DENY == "policy_deny"
    assert AuditEventType.ENFORCEMENT_VIOLATION == "enforcement_violation"
    assert AuditEventType.SINK_FAILURE == "sink_failure"


def test_audit_event_type_serializes_json() -> None:
    assert json.dumps({"type": AuditEventType.POLICY_DENY}) == '{"type": "policy_deny"}'


def test_audit_event_immutable() -> None:
    e = AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.event_type = AuditEventType.POLICY_DENY  # type: ignore[misc]


def test_audit_event_timestamp_default_is_recent_utc() -> None:
    before = datetime.now(UTC)
    e = AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None)
    after = datetime.now(UTC)
    assert before <= e.timestamp <= after
    assert e.timestamp.tzinfo is UTC


def test_audit_event_timestamp_per_instance() -> None:
    """Two consecutive events without explicit timestamp get distinct values."""
    e1 = AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None)
    time.sleep(0.001)
    e2 = AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None)
    assert e1.timestamp < e2.timestamp


def test_audit_event_empty_payload_default() -> None:
    e1 = AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None)
    e2 = AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None)
    assert e1.payload == {}
    assert e2.payload == {}
    # Independent instances — mutating one must not affect the other.
    assert e1.payload is not e2.payload


def test_audit_sink_protocol_isinstance() -> None:
    """A class with a compatible emit() method satisfies the protocol."""

    class _CompliantSink:
        def emit(self, event: AuditEvent) -> None:
            pass

    assert isinstance(_CompliantSink(), AuditSink)


def test_audit_sink_protocol_non_conforming() -> None:
    """A class without emit() does not satisfy the protocol."""

    class _NonCompliant:
        pass

    assert not isinstance(_NonCompliant(), AuditSink)
