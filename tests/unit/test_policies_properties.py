"""Property-based tests for tenantshield.policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tenantshield import (
    Allow,
    AllowListPolicy,
    ChainPolicy,
    Deny,
    DenyByDefaultPolicy,
    Operation,
    OperationType,
    TenantId,
    bind_tenant,
)
from tenantshield.audit import _SINKS_REGISTRY

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tenantshield import Decision


tenant_ids = st.text(min_size=1, max_size=50).map(TenantId)
model_names = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
)


@dataclass(frozen=True)
class _AlwaysAllow:
    """Test helper: a policy that always allows.

    Note: ``slots=True`` is intentionally omitted because empty dataclass +
    slots triggers a CPython bug (same workaround as ``Allow`` in
    ``policies.py``).
    """

    def evaluate(self, _operation: Operation) -> Decision:
        return Allow()


@dataclass(frozen=True, slots=True)
class _AlwaysDeny:
    """Test helper: a policy that always denies with a configurable reason."""

    reason: str = "always deny"

    def evaluate(self, _operation: Operation) -> Decision:
        return Deny(reason=self.reason)


@pytest.fixture(autouse=True)
def _clear_registry() -> Iterator[None]:
    """Defensive: keep the audit registry empty across tests."""
    _SINKS_REGISTRY.clear()
    yield
    _SINKS_REGISTRY.clear()


@given(
    n_allows_before=st.integers(min_value=0, max_value=5),
    n_allows_after=st.integers(min_value=0, max_value=5),
    deny_reason=st.text(min_size=1, max_size=20),
)
@settings(max_examples=100)
def test_chain_policy_with_at_least_one_deny_returns_deny(
    n_allows_before: int, n_allows_after: int, deny_reason: str
) -> None:
    """For any composition with at least one Deny, the chain returns Deny."""
    policies = (
        [_AlwaysAllow()] * n_allows_before
        + [_AlwaysDeny(reason=deny_reason)]
        + [_AlwaysAllow()] * n_allows_after
    )
    chain = ChainPolicy(policies=tuple(policies))
    op = Operation(
        model="app.Model",
        operation_type=OperationType.READ,
        tenant_context=bind_tenant(TenantId("t")),
    )
    result = chain.evaluate(op)
    assert isinstance(result, Deny)
    assert result.reason == deny_reason


@given(
    allowed_models=st.lists(model_names, min_size=1, max_size=10, unique=True).map(frozenset),
    queried_model=model_names,
)
@settings(max_examples=100)
def test_allow_list_policy_denies_unlisted(
    allowed_models: frozenset[str], queried_model: str
) -> None:
    """AllowListPolicy returns Deny exactly when the model is not in the list."""
    policy = AllowListPolicy(allowed_models=allowed_models)
    op = Operation(
        model=queried_model,
        operation_type=OperationType.READ,
        tenant_context=bind_tenant(TenantId("t")),
    )
    result = policy.evaluate(op)

    if queried_model in allowed_models:
        assert isinstance(result, Allow)
    else:
        assert isinstance(result, Deny)


@given(tid=tenant_ids, with_context=st.booleans())
@settings(max_examples=100)
def test_deny_by_default_policy_semantics(tid: TenantId, with_context: bool) -> None:
    """DenyByDefaultPolicy returns Allow iff there is an active context."""
    policy = DenyByDefaultPolicy()
    ctx = bind_tenant(tid) if with_context else None
    op = Operation(
        model="app.Model",
        operation_type=OperationType.READ,
        tenant_context=ctx,
    )
    result = policy.evaluate(op)

    if with_context:
        assert isinstance(result, Allow)
    else:
        assert isinstance(result, Deny)
