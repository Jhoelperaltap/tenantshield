"""Concurrency tests for the tenantshield.audit bus."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from tenantshield import (
    AuditEvent,
    AuditEventType,
    InMemorySink,
    audit_emit,
    register_sink,
    unregister_sink,
)
from tenantshield.audit import _SINKS_REGISTRY

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _clear_registry() -> Iterator[None]:
    """Keep the audit registry empty across tests."""
    _SINKS_REGISTRY.clear()
    yield
    _SINKS_REGISTRY.clear()


class _LockedSink:
    """Thread-safe wrapper around InMemorySink for testing."""

    def __init__(self) -> None:
        self._inner = InMemorySink()
        self._lock = threading.Lock()

    def emit(self, event: AuditEvent) -> None:
        with self._lock:
            self._inner.emit(event)

    @property
    def event_count(self) -> int:
        with self._lock:
            return len(self._inner.events)


def test_registry_chaos_50_threads_converges() -> None:
    """50 threads registering/unregistering chaotically — registry stays coherent.

    Each thread registers its sink, emits some events, then unregisters.
    After all threads finish, the registry must be empty (every register
    paired with an unregister).
    """
    n_threads = 50
    iterations_per_thread = 20
    barrier = threading.Barrier(n_threads)

    def worker(idx: int) -> None:
        sink = InMemorySink()
        barrier.wait()
        for i in range(iterations_per_thread):
            register_sink(sink)
            audit_emit(
                AuditEvent(
                    event_type=AuditEventType.POLICY_ALLOW,
                    tenant_context=None,
                    payload={"thread": idx, "iter": i},
                )
            )
            unregister_sink(sink)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(_SINKS_REGISTRY) == 0


def test_concurrent_emit_to_five_sinks() -> None:
    """10 threads x 100 events x 5 sinks - every event reaches every sink."""
    n_sinks = 5
    n_threads = 10
    events_per_thread = 100
    sinks = [_LockedSink() for _ in range(n_sinks)]
    for sink in sinks:
        register_sink(sink)

    barrier = threading.Barrier(n_threads)

    def worker(idx: int) -> None:
        barrier.wait()
        for i in range(events_per_thread):
            audit_emit(
                AuditEvent(
                    event_type=AuditEventType.CONTEXT_BOUND,
                    tenant_context=None,
                    payload={"thread": idx, "i": i},
                )
            )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected_per_sink = n_threads * events_per_thread
    for sink in sinks:
        assert sink.event_count == expected_per_sink, (
            f"sink got {sink.event_count}, expected {expected_per_sink}"
        )
