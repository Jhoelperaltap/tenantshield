"""Smoke benchmark for the audit bus emit() function.

This is not a pass/fail unit test in the traditional sense — it measures
the latency distribution of dispatching an event to three sinks, and
asserts only a catastrophic-regression ceiling (100us median). The
strict roadmap budget of < 10us applies to the Linux CI baseline (in a
dedicated bench.yml workflow deferred to Sub-phase 1C); local development
on Windows with antivirus active is expected to land in the 10-30us range.

Marked ``slow`` so it can be excluded from the default test run.
"""

from __future__ import annotations

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


@pytest.mark.slow
def test_emit_with_three_sinks_smoke() -> None:
    """Smoke benchmark for emit() with 3 sinks.

    Same rationale as test_context_bench: no strict latency budget is
    enforced on local development machines because system jitter (AV,
    scheduling, frequency scaling) produces variance of 2-3x between
    consecutive runs on the same machine. Instead, a generous catastrophic
    ceiling catches real regressions (I/O introduced into the bus path,
    lock contention, unintended work in dispatch) while tolerating noise.

    The roadmap's < 10us budget for emit() applies to the Linux CI baseline
    in a dedicated bench.yml workflow (deferred to Sub-phase 1C). This
    local test uses 100us as the catastrophic ceiling - 10x the CI budget,
    accommodating realistic Windows jitter.
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

    catastrophic_ceiling_ns = 100_000

    assert median_ns < catastrophic_ceiling_ns, (
        f"emit() median latency {median_ns}ns exceeds catastrophic ceiling "
        f"of {catastrophic_ceiling_ns}ns. p95={p95_ns}ns p99={p99_ns}ns "
        f"over {iterations} iterations with 3 sinks."
    )
