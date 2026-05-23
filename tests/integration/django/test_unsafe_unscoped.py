"""Tests for ADR-0013 three-mode read/write semantics (mode 3: ``_unsafe_unscoped``).

Behavioral coverage of the ``UnsafeUnscopedManager`` write surface:

- Read (``filter`` / ``all``) bypasses the tenant filter without emitting
  audit events.
- Write (``create`` / ``update`` / ``delete`` / ``bulk_create`` /
  ``bulk_update``) bypasses signal validation where applicable and
  emits an ``ENFORCEMENT_BYPASS`` audit event with caller stack context.
- The bypass flag is isolated: normal ``Model.objects`` writes continue
  to validate via ``pre_save`` / ``pre_delete``.
"""

from __future__ import annotations

import pytest

from tenantshield import (
    AuditEventType,
    InMemorySink,
    bind_tenant,
    register_sink,
    tenant_scope,
    unregister_sink,
)
from tenantshield._types import TenantId
from tenantshield.exceptions import CrossTenantAccessError, MissingTenantContextError
from tests.integration.django.testapp.models import Invoice


@pytest.fixture
def audit_sink():
    """Register an InMemorySink and yield it; unregister on teardown."""
    sink = InMemorySink()
    register_sink(sink)
    try:
        yield sink
    finally:
        unregister_sink(sink)


@pytest.mark.django_db
def test_read_bypasses_tenant_filter(invoices) -> None:  # noqa: ARG001
    """``Model._unsafe_unscoped.all()`` returns rows across all tenants."""
    rows = list(Invoice._unsafe_unscoped.all())  # noqa: SLF001
    tenants = {row.tenant_id for row in rows}
    assert tenants == {"acme", "globex"}, f"Expected rows from both tenants, got: {tenants}"


@pytest.mark.django_db
def test_create_succeeds_without_tenant_scope(audit_sink) -> None:  # noqa: ARG001
    """``Model._unsafe_unscoped.create(...)`` works outside ``tenant_scope``.

    The plain ``Model.objects.create(...)`` path would raise
    ``MissingTenantContextError`` here; the bypass manager succeeds.
    """
    invoice = Invoice._unsafe_unscoped.create(  # noqa: SLF001
        tenant_id="acme",
        amount=999,
        description="bypass-create",
    )
    assert invoice.pk is not None
    assert invoice.tenant_id == "acme"


@pytest.mark.django_db
def test_update_succeeds_without_tenant_scope(invoices, audit_sink) -> None:  # noqa: ARG001
    """``Model._unsafe_unscoped.filter(...).update(...)`` works outside scope."""
    affected = Invoice._unsafe_unscoped.filter(  # noqa: SLF001
        tenant_id="acme"
    ).update(description="bypass-updated")
    assert affected >= 1


@pytest.mark.django_db
def test_delete_succeeds_without_tenant_scope(invoices, audit_sink) -> None:  # noqa: ARG001
    """``Model._unsafe_unscoped.filter(...).delete()`` works outside scope.

    Normally ``QuerySet.delete()`` loads instances and fires pre_delete
    per instance; the bypass manager skips that validation.
    """
    deleted, _ = Invoice._unsafe_unscoped.filter(  # noqa: SLF001
        tenant_id="globex"
    ).delete()
    assert deleted >= 1


@pytest.mark.django_db
def test_bulk_create_succeeds_without_tenant_scope(audit_sink) -> None:  # noqa: ARG001
    """``Model._unsafe_unscoped.bulk_create(...)`` works outside scope.

    ``bulk_create`` does not fire ``pre_save`` in Django; the audit
    emission is the only enforcement signal on this path.
    """
    objs = [
        Invoice(tenant_id="acme", amount=10, description="bulk-1"),
        Invoice(tenant_id="globex", amount=20, description="bulk-2"),
    ]
    created = Invoice._unsafe_unscoped.bulk_create(objs)  # noqa: SLF001
    assert len(created) == 2


@pytest.mark.django_db
def test_bulk_update_succeeds_without_tenant_scope(invoices, audit_sink) -> None:  # noqa: ARG001
    """``Model._unsafe_unscoped.bulk_update(...)`` works outside scope."""
    rows = list(Invoice._unsafe_unscoped.filter(tenant_id="acme"))  # noqa: SLF001
    for r in rows:
        r.description = "bulk-updated"
    affected = Invoice._unsafe_unscoped.bulk_update(rows, ["description"])  # noqa: SLF001
    assert affected >= 1
    bypass_events = [
        e for e in audit_sink.events if e.event_type == AuditEventType.ENFORCEMENT_BYPASS
    ]
    # 1 read (filter, no audit) + 1 bulk_update (audited)
    bulk_update_events = [e for e in bypass_events if e.payload["operation"] == "bulk_update"]
    assert len(bulk_update_events) == 1
    assert bulk_update_events[0].payload["operation_context"]["fields"] == ["description"]


@pytest.mark.django_db
def test_create_emits_enforcement_bypass_audit(audit_sink) -> None:
    """Every ``_unsafe_unscoped.create()`` emits an ``ENFORCEMENT_BYPASS`` event."""
    Invoice._unsafe_unscoped.create(  # noqa: SLF001
        tenant_id="acme",
        amount=1,
        description="audit-pin",
    )
    bypass_events = [
        e for e in audit_sink.events if e.event_type == AuditEventType.ENFORCEMENT_BYPASS
    ]
    assert len(bypass_events) == 1
    event = bypass_events[0]
    assert event.payload["operation"] == "create"


@pytest.mark.django_db
def test_audit_payload_contains_model_qualname_and_operation(audit_sink) -> None:
    """Audit payload includes ``model_qualname`` and ``operation`` keys."""
    Invoice._unsafe_unscoped.create(  # noqa: SLF001
        tenant_id="acme",
        amount=2,
        description="payload-shape",
    )
    event = next(e for e in audit_sink.events if e.event_type == AuditEventType.ENFORCEMENT_BYPASS)
    assert "Invoice" in str(event.payload["model_qualname"])
    assert event.payload["operation"] == "create"


@pytest.mark.django_db
def test_audit_payload_contains_caller_stack_frames(audit_sink) -> None:
    """Audit payload includes a ``caller_stack_frames`` list of formatted frames."""
    Invoice._unsafe_unscoped.create(  # noqa: SLF001
        tenant_id="acme",
        amount=3,
        description="stack-pin",
    )
    event = next(e for e in audit_sink.events if e.event_type == AuditEventType.ENFORCEMENT_BYPASS)
    frames = event.payload["caller_stack_frames"]
    assert isinstance(frames, list)
    assert len(frames) >= 1
    # The test function file should appear in the captured stack.
    joined = "".join(str(f) for f in frames)
    assert "test_unsafe_unscoped.py" in joined


@pytest.mark.django_db
def test_audit_captures_current_tenant_when_in_scope(audit_sink) -> None:
    """If the bypass runs inside ``tenant_scope``, the active context is captured."""
    ctx = bind_tenant(TenantId("acme"))
    with tenant_scope(ctx):
        Invoice._unsafe_unscoped.create(  # noqa: SLF001
            tenant_id="acme",
            amount=4,
            description="ctx-capture",
        )
    event = next(e for e in audit_sink.events if e.event_type == AuditEventType.ENFORCEMENT_BYPASS)
    assert event.tenant_context is not None
    assert event.tenant_context.tenant_id == "acme"


@pytest.mark.django_db
def test_audit_tenant_context_is_none_when_outside_scope(audit_sink) -> None:
    """When no scope is active, ``tenant_context`` is ``None`` (by design)."""
    Invoice._unsafe_unscoped.create(  # noqa: SLF001
        tenant_id="globex",
        amount=5,
        description="no-ctx",
    )
    event = next(e for e in audit_sink.events if e.event_type == AuditEventType.ENFORCEMENT_BYPASS)
    assert event.tenant_context is None


@pytest.mark.django_db
def test_signal_bypass_does_not_leak_to_objects_path(audit_sink) -> None:  # noqa: ARG001
    """Normal ``Model.objects`` writes continue to validate via signals.

    After an ``_unsafe_unscoped`` write returns, the bypass flag must be
    reset and subsequent ``Model.objects.create()`` outside ``tenant_scope``
    must raise ``MissingTenantContextError`` again.
    """
    # Bypass write -- should succeed
    Invoice._unsafe_unscoped.create(  # noqa: SLF001
        tenant_id="acme",
        amount=6,
        description="bypass-then-strict",
    )

    # Strict path -- should still raise
    with pytest.raises(MissingTenantContextError):
        Invoice.objects.create(tenant_id="acme", amount=7, description="should-raise")


@pytest.mark.django_db
def test_strict_path_still_blocks_cross_tenant_after_bypass(audit_sink) -> None:  # noqa: ARG001
    """Cross-tenant write detection unaffected by prior bypass operations."""
    Invoice._unsafe_unscoped.create(  # noqa: SLF001
        tenant_id="acme",
        amount=8,
        description="bypass-warmup",
    )

    ctx = bind_tenant(TenantId("acme"))
    with tenant_scope(ctx), pytest.raises(CrossTenantAccessError):
        Invoice.objects.create(
            tenant_id="globex",
            amount=9,
            description="cross-tenant-blocked",
        )
