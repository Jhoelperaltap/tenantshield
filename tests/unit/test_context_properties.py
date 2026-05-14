"""Property-based and concurrency tests for tenant context."""

from __future__ import annotations

import threading

from hypothesis import given, settings
from hypothesis import strategies as st

from tenantshield import (
    TenantId,
    bind_tenant,
    current_tenant,
    tenant_scope,
    try_current_tenant,
)

tenant_ids = st.text(min_size=1, max_size=50).map(TenantId)


@given(tid=tenant_ids)
@settings(max_examples=100)
def test_scope_round_trip(tid: TenantId) -> None:
    """Entering and leaving a scope always restores the prior state."""
    assert try_current_tenant() is None
    with tenant_scope(bind_tenant(tid)):
        assert current_tenant().tenant_id == tid
    assert try_current_tenant() is None


@given(outer=tenant_ids, inner=tenant_ids)
@settings(max_examples=100)
def test_nested_scopes_inner_wins_outer_restored(outer: TenantId, inner: TenantId) -> None:
    """Inner scope shadows outer; on exit, outer is restored."""
    with tenant_scope(bind_tenant(outer)):
        assert current_tenant().tenant_id == outer
        with tenant_scope(bind_tenant(inner)):
            assert current_tenant().tenant_id == inner
        assert current_tenant().tenant_id == outer
    assert try_current_tenant() is None


@given(tids=st.lists(tenant_ids, min_size=1, max_size=5))
@settings(max_examples=50)
def test_deeply_nested_scopes(tids: list[TenantId]) -> None:
    """Arbitrary nesting depth (up to 5) restores correctly."""

    def recurse(remaining: list[TenantId]) -> None:
        if not remaining:
            return
        head, *rest = remaining
        with tenant_scope(bind_tenant(head)):
            assert current_tenant().tenant_id == head
            recurse(rest)
            assert current_tenant().tenant_id == head

    assert try_current_tenant() is None
    recurse(tids)
    assert try_current_tenant() is None


def test_threads_have_isolated_contexts() -> None:
    """Each thread has its own copy of the contextvar; no leakage."""
    results: dict[int, TenantId | None] = {}

    def worker(thread_id: int, tid: TenantId) -> None:
        with tenant_scope(bind_tenant(tid)):
            results[thread_id] = current_tenant().tenant_id

    threads = [
        threading.Thread(target=worker, args=(i, TenantId(f"tenant-{i}"))) for i in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 10
    for i, tid in results.items():
        assert tid == f"tenant-{i}"


def test_main_thread_unaffected_by_worker_thread_scope() -> None:
    """A scope opened in a worker thread does not leak to the main thread."""
    assert try_current_tenant() is None

    def worker() -> None:
        with tenant_scope(bind_tenant(TenantId("worker"))):
            pass

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert try_current_tenant() is None
