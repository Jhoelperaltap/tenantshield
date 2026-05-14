"""Smoke benchmark for the audit bus emit() function.

This is not a pass/fail unit test in the traditional sense - it measures
the latency distribution of dispatching an event to three sinks, and
asserts a ceiling that depends on the execution mode:

- Default (local development): catastrophic ceiling of 100us median.
  Tolerates system jitter on Windows with AV active.
- Strict (CI Linux via ``TENANTSHIELD_BENCH_STRICT=1``): roadmap budget
  of 10us median. Verifies the aspirational performance target on a
  controlled runner.

Marked ``slow`` so it can be excluded from the default test run.
"""

from __future__ import annotations

import os
import statistics
import time

import pytest

from tenantshield import (
    AuditEvent,
    AuditEventType,
    InMemorySink,
    audit_emit,
    register_sink,
    unregister_sink,
)

_STRICT_MODE = os.environ.get("TENANTSHIELD_BENCH_STRICT") == "1"
_CEILING_NS = 10_000 if _STRICT_MODE else 100_000


@pytest.mark.slow
def test_emit_with_three_sinks_smoke() -> None:
    """Smoke benchmark for emit() with 3 sinks.

    Two modes selected via the ``TENANTSHIELD_BENCH_STRICT`` environment
    variable:

    - Local (default): catastrophic ceiling of 100us median - tolerates
      system jitter.
    - Strict (CI Linux): roadmap budget of 10us median - verifies the
      aspirational performance target on a controlled runner.
    """
    iterations = 10_000
    sinks = [InMemorySink() for _ in range(3)]
    for sink in sinks:
        register_sink(sink)

    event = AuditEvent(
        event_type=AuditEventType.POLICY_ALLOW,
        tenant_context=None,
    )

    try:
        samples_ns: list[int] = []
        for _ in range(iterations):
            start = time.perf_counter_ns()
            audit_emit(event)
            samples_ns.append(time.perf_counter_ns() - start)
    finally:
        for sink in sinks:
            unregister_sink(sink)

    median_ns = statistics.median(samples_ns)
    p95_ns = statistics.quantiles(samples_ns, n=20)[18]
    p99_ns = statistics.quantiles(samples_ns, n=100)[98]

    mode_label = "strict CI" if _STRICT_MODE else "local catastrophic"
    assert median_ns < _CEILING_NS, (
        f"emit() median latency {median_ns}ns exceeds {mode_label} ceiling "
        f"of {_CEILING_NS}ns. p95={p95_ns}ns p99={p99_ns}ns "
        f"over {iterations} iterations with 3 sinks."
    )
