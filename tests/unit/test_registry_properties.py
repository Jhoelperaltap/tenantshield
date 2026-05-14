"""Property-based tests for tenantshield.registry."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tenantshield.registry import ModelRegistry


@given(n=st.integers(min_value=1, max_value=50))
@settings(max_examples=100)
def test_register_n_distinct_models(n: int) -> None:
    """Registering n distinct models yields a registry of size n."""
    registry = ModelRegistry()
    classes = [type(f"_M{i}", (), {}) for i in range(n)]
    for cls in classes:
        registry.register(cls)
    assert len(registry) == n


@given(
    n=st.integers(min_value=1, max_value=20),
    m=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=100)
def test_register_and_unregister(n: int, m: int) -> None:
    """Register n, unregister min(m, n), size is n - min(m, n)."""
    registry = ModelRegistry()
    classes = [type(f"_M{i}", (), {}) for i in range(n)]
    for cls in classes:
        registry.register(cls)
    for cls in classes[: min(m, n)]:
        registry.unregister(cls)
    assert len(registry) == n - min(m, n)


@given(k=st.integers(min_value=1, max_value=20))
@settings(max_examples=100)
def test_register_idempotent_k_times(k: int) -> None:
    """Registering the same model k times yields a registry of size 1."""
    registry = ModelRegistry()

    class _M:
        """Test model."""

    for _ in range(k):
        registry.register(_M)
    assert len(registry) == 1
