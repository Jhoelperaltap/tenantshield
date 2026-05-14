"""Top-level pytest configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tenantshield.audit import (
    _SINKS_REGISTRY,
    InMemorySink,
    NullSink,
    register_sink,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def silent_audit() -> Iterator[NullSink]:
    """Provide an isolated audit bus for the test.

    Snapshots the current registry, replaces it with a single ``NullSink``
    for the duration of the test, and restores the original on teardown.

    Yields:
        The ``NullSink`` instance (rarely needed, but available).
    """
    original = list(_SINKS_REGISTRY)
    _SINKS_REGISTRY.clear()
    null = NullSink()
    register_sink(null)
    try:
        yield null
    finally:
        _SINKS_REGISTRY.clear()
        for sink in original:
            register_sink(sink)


@pytest.fixture
def capture_audit() -> Iterator[InMemorySink]:
    """Provide an ``InMemorySink`` wired into an isolated audit bus.

    Like ``silent_audit`` but yields an ``InMemorySink`` so the test can
    inspect emitted events.

    Yields:
        The ``InMemorySink`` instance.
    """
    original = list(_SINKS_REGISTRY)
    _SINKS_REGISTRY.clear()
    sink = InMemorySink()
    register_sink(sink)
    try:
        yield sink
    finally:
        _SINKS_REGISTRY.clear()
        for sink_to_restore in original:
            register_sink(sink_to_restore)
