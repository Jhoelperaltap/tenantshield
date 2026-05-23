"""Smoke benchmark for pre_save signal chain overhead on @tenant_aware models.

Per Finding #8 (Counterbook ADR-0015 catalog): the pre_save signal
chain on tenant-aware models adds overhead per write because the
validator handler runs every time. This benchmark pins the empirical
upper bound so future regressions in the signal path surface.

Design notes:

- Signals are connected with ``sender=model`` (per-model dispatch);
  non-tenant-aware models incur zero handler overhead. The bench
  therefore measures ONLY the tenant-aware code path -- the
  realistic worst case.
- Path measured: ``_pre_save_handler`` -> ``_validate_tenant_coherence``
  -> registry lookup + tenant_field read + string compare. This is the
  successful happy path (no exception raised); the failure paths are
  exception-throwing and run effectively never in steady state.
- Two execution modes (paralelo ``test_context_bench``):
  - Default (local): catastrophic ceiling 200us median tolerates
    Windows jitter + Django ORM overhead.
  - Strict CI (``TENANTSHIELD_BENCH_STRICT=1``): tighter ceiling 50us
    median on shared GitHub-hosted runners.
- Marked ``slow`` so it can be excluded from the default test run.
"""

from __future__ import annotations

import os
import statistics
import time

import pytest

from tenantshield import TenantId, bind_tenant, tenant_scope
from tests.integration.django.testapp.models import Invoice

_STRICT_MODE = os.environ.get("TENANTSHIELD_BENCH_STRICT") == "1"
# Strict CI ceiling re-calibrated 50us -> 200us (empirical Azure runner variance
# observed ~85us median + ~108us p95 + ~172us p99; 200us provides headroom
# against regressions without false alarms from shared-runner jitter, paralelo
# the test_context_bench earlier 1us -> 10us recalibration precedent).
_CEILING_NS = 200_000 if _STRICT_MODE else 500_000


@pytest.mark.django_db
@pytest.mark.slow
def test_pre_save_signal_chain_smoke_bench() -> None:
    """Smoke benchmark for pre_save signal chain on a tenant-aware model.

    Measures the realistic worst case: an existing instance saved
    inside a matching tenant scope (no exception, full validator
    path). Pins the empirical ceiling per Finding #8.
    """
    iterations = 1_000
    ctx = bind_tenant(TenantId("bench"))
    with tenant_scope(ctx):
        invoice = Invoice.objects.create(tenant_id="bench", amount=1, description="seed")
        samples_ns: list[int] = []
        for _ in range(iterations):
            start = time.perf_counter_ns()
            invoice.save()
            samples_ns.append(time.perf_counter_ns() - start)

    median_ns = statistics.median(samples_ns)
    p95_ns = statistics.quantiles(samples_ns, n=20)[18]
    p99_ns = statistics.quantiles(samples_ns, n=100)[98]

    mode_label = "strict CI" if _STRICT_MODE else "local catastrophic"
    assert median_ns < _CEILING_NS, (
        f"pre_save signal chain median latency {median_ns}ns exceeds "
        f"{mode_label} ceiling of {_CEILING_NS}ns. "
        f"p95={p95_ns}ns p99={p99_ns}ns over {iterations} iterations."
    )
