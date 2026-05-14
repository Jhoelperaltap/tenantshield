"""Tests for tenantshield.registry — RegistryEntry and ModelRegistry."""

from __future__ import annotations

import dataclasses
import threading

import pytest

from tenantshield.exceptions import ConfigurationError
from tenantshield.registry import ModelRegistry, RegistryEntry


class _ModelA:
    """Dummy model class for registry tests."""


class _ModelB:
    """Dummy model class for registry tests."""


class _ModelC:
    """Dummy model class for registry tests."""


def test_registry_entry_immutable() -> None:
    entry = RegistryEntry(model=_ModelA, tenant_field="tenant_id")
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.tenant_field = "org_id"  # type: ignore[misc]


def test_registry_starts_empty() -> None:
    registry = ModelRegistry()
    assert len(registry) == 0
    assert not registry.is_registered(_ModelA)


def test_register_adds_entry() -> None:
    registry = ModelRegistry()
    registry.register(_ModelA)
    assert registry.is_registered(_ModelA)
    assert len(registry) == 1


def test_register_idempotent_same_field() -> None:
    """Registering the same model twice with same tenant_field is a no-op."""
    registry = ModelRegistry()
    registry.register(_ModelA)
    registry.register(_ModelA)
    assert len(registry) == 1


def test_register_idempotent_same_explicit_field() -> None:
    """Same idempotency holds when tenant_field is explicit."""
    registry = ModelRegistry()
    registry.register(_ModelA, tenant_field="org_id")
    registry.register(_ModelA, tenant_field="org_id")
    assert len(registry) == 1
    assert registry.get(_ModelA).tenant_field == "org_id"


def test_register_conflict_different_field() -> None:
    """Re-registering with a different tenant_field raises ConfigurationError."""
    registry = ModelRegistry()
    registry.register(_ModelA, tenant_field="tenant_id")

    with pytest.raises(ConfigurationError) as exc_info:
        registry.register(_ModelA, tenant_field="org_id")

    msg = str(exc_info.value)
    assert "tenant_id" in msg
    assert "org_id" in msg
    assert "_ModelA" in msg


def test_unregister_removes() -> None:
    registry = ModelRegistry()
    registry.register(_ModelA)
    registry.unregister(_ModelA)
    assert not registry.is_registered(_ModelA)
    assert len(registry) == 0


def test_unregister_unregistered_is_noop() -> None:
    registry = ModelRegistry()
    registry.unregister(_ModelA)  # never registered
    assert len(registry) == 0


def test_get_returns_entry() -> None:
    registry = ModelRegistry()
    registry.register(_ModelA, tenant_field="account_id")
    entry = registry.get(_ModelA)
    assert entry.model is _ModelA
    assert entry.tenant_field == "account_id"


def test_get_unregistered_raises() -> None:
    registry = ModelRegistry()
    with pytest.raises(ConfigurationError) as exc_info:
        registry.get(_ModelA)
    assert "_ModelA" in str(exc_info.value)
    assert "not registered" in str(exc_info.value).lower()


def test_iter_yields_entries() -> None:
    """Iteration yields all registered entries."""
    registry = ModelRegistry()
    registry.register(_ModelA)
    registry.register(_ModelB)
    registry.register(_ModelC)

    entries = list(registry)
    assert len(entries) == 3
    models = {entry.model for entry in entries}
    assert models == {_ModelA, _ModelB, _ModelC}


def test_clear_empties_registry() -> None:
    registry = ModelRegistry()
    registry.register(_ModelA)
    registry.register(_ModelB)
    registry.clear()
    assert len(registry) == 0
    assert not registry.is_registered(_ModelA)


def test_register_thread_safety() -> None:
    """10 threads registering distinct models — all end up registered."""
    registry = ModelRegistry()
    model_classes = [type(f"_M{i}", (), {}) for i in range(10)]
    barrier = threading.Barrier(10)

    def worker(model_cls: type) -> None:
        barrier.wait()
        registry.register(model_cls)

    threads = [threading.Thread(target=worker, args=(cls,)) for cls in model_classes]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(registry) == 10
    for cls in model_classes:
        assert registry.is_registered(cls)
