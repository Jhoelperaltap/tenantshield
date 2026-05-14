"""Tests for tenantshield.audit registry, emit, and SINK_FAILURE handling."""

from __future__ import annotations

import threading

import pytest

from tenantshield.audit import (
    _SINKS_REGISTRY,
    AuditEvent,
    AuditEventType,
    InMemorySink,
    emit,
    register_sink,
    unregister_sink,
)


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Ensure each test starts and ends with an empty registry."""
    _SINKS_REGISTRY.clear()
    yield
    _SINKS_REGISTRY.clear()


class _FailingSink:
    """Test helper: a sink that raises on every emit, counting calls."""

    def __init__(self) -> None:
        self.call_count = 0
        self.last_event_type: AuditEventType | None = None

    def emit(self, event: AuditEvent) -> None:
        self.call_count += 1
        self.last_event_type = event.event_type
        msg = f"sink failed on {event.event_type.value}"
        raise RuntimeError(msg)


class _LockedSink:
    """Test helper: thread-safe wrapper around InMemorySink."""

    def __init__(self) -> None:
        self._inner = InMemorySink()
        self._lock = threading.Lock()

    def emit(self, event: AuditEvent) -> None:
        with self._lock:
            self._inner.emit(event)

    @property
    def events(self) -> list[AuditEvent]:
        with self._lock:
            return list(self._inner.events)


def test_register_sink_appends() -> None:
    sink = InMemorySink()
    register_sink(sink)
    assert sink in _SINKS_REGISTRY
    assert len(_SINKS_REGISTRY) == 1


def test_register_sink_idempotent() -> None:
    sink = InMemorySink()
    register_sink(sink)
    register_sink(sink)
    register_sink(sink)
    assert _SINKS_REGISTRY.count(sink) == 1


def test_unregister_sink_removes() -> None:
    sink = InMemorySink()
    register_sink(sink)
    unregister_sink(sink)
    assert sink not in _SINKS_REGISTRY
    assert len(_SINKS_REGISTRY) == 0


def test_unregister_unregistered_is_noop() -> None:
    sink = InMemorySink()
    # Never registered.
    unregister_sink(sink)  # must not raise
    assert len(_SINKS_REGISTRY) == 0


def test_emit_with_empty_registry() -> None:
    # No sinks registered; emit must not raise.
    emit(AuditEvent(event_type=AuditEventType.CONTEXT_BOUND, tenant_context=None))


def test_emit_dispatches_to_all_sinks() -> None:
    sinks = [InMemorySink() for _ in range(3)]
    for sink in sinks:
        register_sink(sink)

    event = AuditEvent(event_type=AuditEventType.POLICY_ALLOW, tenant_context=None)
    emit(event)

    for sink in sinks:
        assert sink.events == [event]


def test_emit_failing_sink_does_not_break_others() -> None:
    """When sink B fails, sinks A and C still receive both events."""
    sink_a = InMemorySink()
    sink_b = _FailingSink()
    sink_c = InMemorySink()
    register_sink(sink_a)
    register_sink(sink_b)
    register_sink(sink_c)

    original = AuditEvent(event_type=AuditEventType.POLICY_ALLOW, tenant_context=None)
    emit(original)

    # Both A and C see the original event.
    assert original in sink_a.events
    assert original in sink_c.events

    # Both A and C also see a SINK_FAILURE event for sink_b.
    a_failure_events = [e for e in sink_a.events if e.event_type == AuditEventType.SINK_FAILURE]
    c_failure_events = [e for e in sink_c.events if e.event_type == AuditEventType.SINK_FAILURE]
    assert len(a_failure_events) == 1
    assert len(c_failure_events) == 1

    # The failure payload identifies sink_b.
    assert a_failure_events[0].payload["failing_sink_type"] == "_FailingSink"
    assert a_failure_events[0].payload["original_event_type"] == "policy_allow"
    assert a_failure_events[0].payload["error_type"] == "RuntimeError"


def test_emit_sink_failure_excludes_failing_sink() -> None:
    """The sink that failed does NOT receive the SINK_FAILURE event for itself."""
    sink_a = InMemorySink()
    sink_b = _FailingSink()
    register_sink(sink_a)
    register_sink(sink_b)

    emit(AuditEvent(event_type=AuditEventType.POLICY_ALLOW, tenant_context=None))

    # sink_b was called exactly once — with the original event, not with its own failure.
    assert sink_b.call_count == 1
    assert sink_b.last_event_type == AuditEventType.POLICY_ALLOW


def test_emit_double_failure_suppressed() -> None:
    """Two failing sinks do not cause unhandled errors or infinite recursion."""
    sink_a = _FailingSink()
    sink_b = _FailingSink()
    register_sink(sink_a)
    register_sink(sink_b)

    # This MUST NOT raise.
    emit(AuditEvent(event_type=AuditEventType.POLICY_ALLOW, tenant_context=None))

    # Each sink receives:
    #   1) the original POLICY_ALLOW event (direct dispatch)
    #   2) the SINK_FAILURE for the OTHER sink (cross-notification)
    # The SINK_FAILURE for itself is excluded by _emit_sink_failure.
    # Second-level failures are suppressed.
    assert sink_a.call_count == 2
    assert sink_b.call_count == 2


def test_register_unregister_thread_safety() -> None:
    """Concurrent register/unregister leave the registry coherent."""
    n_threads = 10
    iterations_per_thread = 100
    barrier = threading.Barrier(n_threads)
    sinks = [InMemorySink() for _ in range(n_threads)]

    def worker(sink: InMemorySink) -> None:
        barrier.wait()
        for _ in range(iterations_per_thread):
            register_sink(sink)
            unregister_sink(sink)
        register_sink(sink)  # final state: registered

    threads = [threading.Thread(target=worker, args=(sink,)) for sink in sinks]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(_SINKS_REGISTRY) == n_threads
    for sink in sinks:
        assert sink in _SINKS_REGISTRY
    assert len({id(s) for s in _SINKS_REGISTRY}) == n_threads


def test_emit_thread_safety() -> None:
    """Concurrent emits to a thread-safe sink deliver all events."""
    sink = _LockedSink()
    register_sink(sink)

    n_threads = 10
    events_per_thread = 50
    barrier = threading.Barrier(n_threads)

    def worker() -> None:
        barrier.wait()
        for i in range(events_per_thread):
            emit(
                AuditEvent(
                    event_type=AuditEventType.POLICY_ALLOW,
                    tenant_context=None,
                    payload={"i": i},
                )
            )

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(sink.events) == n_threads * events_per_thread
