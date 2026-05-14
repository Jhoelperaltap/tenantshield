"""Smoke benchmark for tenant scope entry/exit overhead.

This is not a pass/fail unit test in the traditional sense - it measures
the latency distribution of entering and exiting a sync scope, and asserts
a ceiling that depends on the execution mode:

- Default (local development): catastrophic ceiling of 50us median.
  Tolerates Windows jitter, AV scanning, frequency scaling.
- Strict (CI Linux via ``TENANTSHIELD_BENCH_STRICT=1``): roadmap budget
  of 1us median. Verifies the aspirational performance target on a
  controlled runner.

Marked ``slow`` so it can be excluded from the default test run.
"""

from __future__ import annotations

import os
import statistics
import time

import pytest

from tenantshield import TenantId, bind_tenant, tenant_scope

_STRICT_MODE = os.environ.get("TENANTSHIELD_BENCH_STRICT") == "1"
_CEILING_NS = 1_000 if _STRICT_MODE else 50_000


@pytest.mark.slow
def test_tenant_scope_entry_exit_smoke() -> None:
    """Smoke benchmark for tenant scope entry/exit latency.

    Two modes selected via the ``TENANTSHIELD_BENCH_STRICT`` environment
    variable:

    - Local (default): catastrophic ceiling of 50us median - tolerates
      system jitter.
    - Strict (CI Linux): roadmap budget of 1us median - verifies the
      aspirational performance target on a controlled runner.
    """
    iterations = 10_000
    ctx = bind_tenant(TenantId("bench"))

    samples_ns: list[int] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        with tenant_scope(ctx):
            pass
        samples_ns.append(time.perf_counter_ns() - start)

    median_ns = statistics.median(samples_ns)
    p95_ns = statistics.quantiles(samples_ns, n=20)[18]
    p99_ns = statistics.quantiles(samples_ns, n=100)[98]

    mode_label = "strict CI" if _STRICT_MODE else "local catastrophic"
    assert median_ns < _CEILING_NS, (
        f"tenant_scope median entry/exit latency {median_ns}ns exceeds "
        f"{mode_label} ceiling of {_CEILING_NS}ns. "
        f"p95={p95_ns}ns p99={p99_ns}ns over {iterations} iterations."
    )
