"""Tenant enforcement policies for TenantShield.

This module defines the :class:`Policy` protocol, the three :class:`Decision`
variants (``Allow``, ``Deny``, ``RequireScope``), and three built-in policies
(``DenyByDefaultPolicy``, ``AllowListPolicy``, ``ChainPolicy``). The
:func:`evaluate_and_audit` helper composes a policy evaluation with an audit
emission.

Policies are pure — they do not perform I/O or emit events by themselves.
The audit emission is the responsibility of :func:`evaluate_and_audit` or
of adapters in Phase 2+.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, assert_never, runtime_checkable

from tenantshield.audit import AuditEvent, AuditEventType, emit

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tenantshield.context import TenantContext


def _empty_extras() -> dict[str, object]:
    """Factory for the default empty extras of Operation."""
    return {}


class OperationType(StrEnum):
    """Kind of operation being evaluated by a policy.

    Inherits from ``str`` so it serializes cleanly to JSON.
    """

    READ = "read"
    WRITE = "write"
    DELETE = "delete"


@dataclass(frozen=True, slots=True, kw_only=True)
class Operation:
    """Describes an operation to be evaluated by a policy.

    Attributes:
        model: Fully-qualified model name (e.g. ``"app.Invoice"``).
        operation_type: Kind of operation.
        tenant_context: The tenant context active during evaluation, or
            ``None`` if no context is active.
        extras: Arbitrary additional data for custom policies.
    """

    model: str
    operation_type: OperationType
    tenant_context: TenantContext | None
    extras: Mapping[str, object] = field(default_factory=_empty_extras)


@dataclass(frozen=True)
class Allow:
    """Decision: allow the operation.

    Note: ``slots=True`` is intentionally omitted because ``frozen=True`` +
    ``slots=True`` on a dataclass with no fields triggers a CPython bug
    (TypeError instead of FrozenInstanceError on setattr). Slots add no
    benefit to an empty class, so we keep this class non-slotted while
    ``Deny`` and ``RequireScope`` (which have fields) remain slotted.
    """


@dataclass(frozen=True, slots=True)
class Deny:
    """Decision: deny the operation.

    Attributes:
        reason: Human-readable reason. Surfaces in audit logs.
    """

    reason: str


@dataclass(frozen=True, slots=True)
class RequireScope:
    """Decision: allow only if scoped by the given filter spec.

    Attributes:
        filter_spec: Mapping of constraints. In Sub-phase 1B this is a
            free-form dict; adapters in Phase 2+ may impose structure.
    """

    filter_spec: Mapping[str, object]


Decision = Allow | Deny | RequireScope


@runtime_checkable
class Policy(Protocol):
    """Contract for tenant enforcement policies.

    Implementations should be stateless or stateful but thread-safe.
    Policies must not perform I/O — they receive the operation and return
    a decision synchronously.
    """

    def evaluate(self, operation: Operation) -> Decision: ...  # pragma: no cover


@dataclass(frozen=True, slots=True)
class DenyByDefaultPolicy:
    """A policy that denies any operation without an active tenant context.

    If a tenant context IS active, the operation is allowed. This is the
    minimal enforcement: prevent operations from running in the absence
    of explicit tenancy.
    """

    def evaluate(self, operation: Operation) -> Decision:
        if operation.tenant_context is None:
            return Deny(
                reason=(
                    f"No tenant context active for "
                    f"{operation.operation_type.value} on {operation.model!r}"
                )
            )
        return Allow()


@dataclass(frozen=True, slots=True)
class AllowListPolicy:
    """A policy that allows operations only on a fixed set of models.

    Operations on models outside the allowlist are denied regardless of
    tenant context. Operations on allowlisted models still require tenant
    context (delegate that to ``DenyByDefaultPolicy`` via composition).

    Attributes:
        allowed_models: Frozen set of fully-qualified model names.
    """

    allowed_models: frozenset[str]

    def evaluate(self, operation: Operation) -> Decision:
        if operation.model not in self.allowed_models:
            return Deny(reason=f"Model {operation.model!r} is not in the allowlist")
        return Allow()


@dataclass(frozen=True, slots=True)
class ChainPolicy:
    """Compose multiple policies; first non-Allow decision wins.

    Iterates the policies in order. If any returns ``Deny`` or
    ``RequireScope``, the chain returns that decision (subsequent policies
    are not evaluated). Only if all policies return ``Allow`` does the chain
    return ``Allow``.

    Attributes:
        policies: Tuple of policies to apply in order.
    """

    policies: tuple[Policy, ...]

    def evaluate(self, operation: Operation) -> Decision:
        for policy in self.policies:
            decision = policy.evaluate(operation)
            match decision:
                case Allow():
                    continue
                case Deny() | RequireScope():
                    return decision
                case _:  # pragma: no cover
                    assert_never(decision)
        return Allow()


def evaluate_and_audit(policy: Policy, operation: Operation) -> Decision:
    """Evaluate ``operation`` against ``policy`` and emit an audit event.

    Emits ``POLICY_ALLOW`` or ``POLICY_DENY`` based on the decision.
    ``RequireScope`` decisions emit ``POLICY_ALLOW`` (the scope is
    informational, not a denial).

    Args:
        policy: The policy to evaluate.
        operation: The operation to evaluate.

    Returns:
        The decision returned by the policy.
    """
    decision = policy.evaluate(operation)
    match decision:
        case Allow() | RequireScope():
            event_type = AuditEventType.POLICY_ALLOW
        case Deny():
            event_type = AuditEventType.POLICY_DENY
        case _:  # pragma: no cover
            assert_never(decision)

    emit(
        AuditEvent(
            event_type=event_type,
            tenant_context=operation.tenant_context,
            payload={
                "model": operation.model,
                "operation_type": operation.operation_type.value,
                "decision_type": type(decision).__name__,
                "decision_data": _decision_to_payload(decision),
            },
        )
    )
    return decision


def _decision_to_payload(decision: Decision) -> dict[str, object]:
    """Serialize a Decision into a dict for audit payload."""
    match decision:
        case Allow():
            return {}
        case Deny(reason=reason):
            return {"reason": reason}
        case RequireScope(filter_spec=filter_spec):
            return {"filter_spec": dict(filter_spec)}
        case _:  # pragma: no cover
            assert_never(decision)


__all__ = [
    "Allow",
    "AllowListPolicy",
    "ChainPolicy",
    "Decision",
    "Deny",
    "DenyByDefaultPolicy",
    "Operation",
    "OperationType",
    "Policy",
    "RequireScope",
    "evaluate_and_audit",
]
