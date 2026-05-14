"""Concurrency tests for tenantshield.registry."""

from __future__ import annotations

import threading

from tenantshield.registry import ModelRegistry


def test_registry_chaos_30_threads_converges() -> None:
    """30 threads doing register/unregister/queries - registry stays coherent.

    Each thread owns its own model class and cycles register -> query ->
    unregister. After all threads finish, the registry must be empty
    (every register paired with an unregister).
    """
    registry = ModelRegistry()
    n_threads = 30
    iterations_per_thread = 50

    barrier = threading.Barrier(n_threads)

    def worker(idx: int) -> None:
        model_cls = type(f"_M{idx}", (), {})
        barrier.wait()
        for _ in range(iterations_per_thread):
            registry.register(model_cls)
            assert registry.is_registered(model_cls)
            _ = registry.get(model_cls)  # exercise read path under contention
            registry.unregister(model_cls)
            assert not registry.is_registered(model_cls)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(registry) == 0
