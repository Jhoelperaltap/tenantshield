"""Tests for tenantshield.policies."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, assert_never

import pytest

from tenantshield import TenantId, bind_tenant
from tenantshield.audit import AuditEventType
from tenantshield.policies import (
    Allow,
    AllowListPolicy,
    ChainPolicy,
    Decision,
    Deny,
    DenyByDefaultPolicy,
    Operation,
    OperationType,
    RequireScope,
    evaluate_and_audit,
)

if TYPE_CHECKING:
    from tenantshield.audit import InMemorySink


def test_operation_immutable() -> None:
    op = Operation(
        model="app.X",
        operation_type=OperationType.READ,
        tenant_context=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        op.model = "app.Y"  # type: ignore[misc]


def test_operation_type_enum_values() -> None:
    assert OperationType.READ == "read"
    assert OperationType.WRITE == "write"
    assert OperationType.DELETE == "delete"


def test_allow_equality_and_immutable() -> None:
    assert Allow() == Allow()
    a = Allow()
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.foo = "bar"  # type: ignore[misc]


def test_deny_carries_reason_and_immutable() -> None:
    d = Deny(reason="no")
    assert d.reason == "no"
    assert Deny(reason="no") == Deny(reason="no")
    assert Deny(reason="x") != Deny(reason="y")
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.reason = "x"  # type: ignore[misc]


def test_require_scope_carries_filter_spec_and_immutable() -> None:
    r = RequireScope(filter_spec={"region": "eu"})
    assert r.filter_spec == {"region": "eu"}
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.filter_spec = {}  # type: ignore[misc]


def test_decision_match_exhaustive() -> None:
    """A consumer using match with assert_never handles all Decision cases."""

    def classify(d: Decision) -> str:
        match d:
            case Allow():
                return "allow"
            case Deny(reason=r):
                return f"deny:{r}"
            case RequireScope(filter_spec=spec):
                return f"scope:{len(spec)}"
            case _:  # pragma: no cover
                assert_never(d)

    assert classify(Allow()) == "allow"
    assert classify(Deny(reason="x")) == "deny:x"
    assert classify(RequireScope(filter_spec={"k": "v"})) == "scope:1"


def test_deny_by_default_policy_allows_with_context() -> None:
    policy = DenyByDefaultPolicy()
    op = Operation(
        model="app.X",
        operation_type=OperationType.READ,
        tenant_context=bind_tenant(TenantId("acme")),
    )
    assert isinstance(policy.evaluate(op), Allow)


def test_deny_by_default_policy_denies_without_context() -> None:
    policy = DenyByDefaultPolicy()
    op = Operation(
        model="app.X",
        operation_type=OperationType.READ,
        tenant_context=None,
    )
    decision = policy.evaluate(op)
    assert isinstance(decision, Deny)
    assert "tenant context" in decision.reason.lower()


def test_allow_list_policy_allows_listed_model() -> None:
    policy = AllowListPolicy(allowed_models=frozenset({"app.Invoice", "app.User"}))
    op = Operation(
        model="app.Invoice",
        operation_type=OperationType.READ,
        tenant_context=None,
    )
    assert isinstance(policy.evaluate(op), Allow)


def test_allow_list_policy_denies_unlisted_model() -> None:
    policy = AllowListPolicy(allowed_models=frozenset({"app.Invoice"}))
    op = Operation(
        model="other.Model",
        operation_type=OperationType.READ,
        tenant_context=None,
    )
    decision = policy.evaluate(op)
    assert isinstance(decision, Deny)
    assert "allowlist" in decision.reason.lower()


def test_chain_policy_first_deny_wins() -> None:
    chain = ChainPolicy(policies=(DenyByDefaultPolicy(),))
    op = Operation(
        model="app.X",
        operation_type=OperationType.READ,
        tenant_context=None,
    )
    decision = chain.evaluate(op)
    assert isinstance(decision, Deny)


def test_chain_policy_all_allow_returns_allow() -> None:
    chain = ChainPolicy(
        policies=(
            AllowListPolicy(allowed_models=frozenset({"app.X"})),
            DenyByDefaultPolicy(),
        )
    )
    op = Operation(
        model="app.X",
        operation_type=OperationType.READ,
        tenant_context=bind_tenant(TenantId("acme")),
    )
    assert isinstance(chain.evaluate(op), Allow)


def test_chain_policy_require_scope_short_circuits() -> None:
    """A RequireScope from one policy stops further evaluation."""

    @dataclasses.dataclass(frozen=True, slots=True)
    class _ScopingPolicy:
        def evaluate(self, _operation: Operation) -> Decision:
            return RequireScope(filter_spec={"region": "eu"})

    @dataclasses.dataclass(frozen=True, slots=True)
    class _AlwaysDenyPolicy:
        def evaluate(self, _operation: Operation) -> Decision:
            return Deny(reason="should not be reached")

    chain = ChainPolicy(policies=(_ScopingPolicy(), _AlwaysDenyPolicy()))
    op = Operation(
        model="app.X",
        operation_type=OperationType.READ,
        tenant_context=None,
    )
    decision = chain.evaluate(op)
    assert isinstance(decision, RequireScope)


def test_chain_policy_empty_returns_allow() -> None:
    chain = ChainPolicy(policies=())
    op = Operation(
        model="app.X",
        operation_type=OperationType.READ,
        tenant_context=None,
    )
    assert isinstance(chain.evaluate(op), Allow)


def test_evaluate_and_audit_emits_allow(capture_audit: InMemorySink) -> None:
    policy = DenyByDefaultPolicy()
    ctx = bind_tenant(TenantId("acme"))
    op = Operation(
        model="app.Invoice",
        operation_type=OperationType.READ,
        tenant_context=ctx,
    )
    decision = evaluate_and_audit(policy, op)

    assert isinstance(decision, Allow)
    assert len(capture_audit.events) == 1
    assert capture_audit.events[0].event_type == AuditEventType.POLICY_ALLOW
    assert capture_audit.events[0].payload["decision_type"] == "Allow"


def test_evaluate_and_audit_emits_deny(capture_audit: InMemorySink) -> None:
    policy = DenyByDefaultPolicy()
    op = Operation(
        model="app.Invoice",
        operation_type=OperationType.READ,
        tenant_context=None,
    )
    decision = evaluate_and_audit(policy, op)

    assert isinstance(decision, Deny)
    assert len(capture_audit.events) == 1
    assert capture_audit.events[0].event_type == AuditEventType.POLICY_DENY
    assert capture_audit.events[0].payload["decision_type"] == "Deny"
    decision_data = capture_audit.events[0].payload["decision_data"]
    assert isinstance(decision_data, dict)
    assert "reason" in decision_data


def test_evaluate_and_audit_emits_allow_for_require_scope(
    capture_audit: InMemorySink,
) -> None:
    """RequireScope is treated as POLICY_ALLOW with scope info in payload."""

    @dataclasses.dataclass(frozen=True, slots=True)
    class _ScopingPolicy:
        def evaluate(self, _operation: Operation) -> Decision:
            return RequireScope(filter_spec={"region": "eu"})

    op = Operation(
        model="app.Invoice",
        operation_type=OperationType.READ,
        tenant_context=bind_tenant(TenantId("acme")),
    )
    decision = evaluate_and_audit(_ScopingPolicy(), op)

    assert isinstance(decision, RequireScope)
    assert capture_audit.events[0].event_type == AuditEventType.POLICY_ALLOW
    assert capture_audit.events[0].payload["decision_type"] == "RequireScope"
    assert capture_audit.events[0].payload["decision_data"] == {"filter_spec": {"region": "eu"}}


def test_evaluate_and_audit_payload_includes_decision_data(
    capture_audit: InMemorySink,
) -> None:
    policy = DenyByDefaultPolicy()
    op = Operation(
        model="app.X",
        operation_type=OperationType.WRITE,
        tenant_context=None,
    )
    evaluate_and_audit(policy, op)

    payload = capture_audit.events[0].payload
    assert payload["model"] == "app.X"
    assert payload["operation_type"] == "write"
    assert payload["decision_type"] == "Deny"
    assert isinstance(payload["decision_data"], dict)
