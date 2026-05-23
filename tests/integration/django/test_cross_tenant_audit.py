"""Tests for cross-tenant ``.update()``/``.delete()`` audit emission (Finding #1 SOC2 BLOCKER).

Validates ADR-0013 dual-dispatch detection: when a model is decorated
with ``@tenant_aware(audit_cross_tenant_attempts=True)``, every
``Model.objects.filter(...).update(...)`` and ``.delete()`` operation
performs a pre-flight unscoped query to detect PKs that match the
caller's filters but belong to OTHER tenants. Each such attempt emits
an ``ENFORCEMENT_VIOLATION`` audit event with attempted PKs + caller
stack frames.

The detection is opt-in (off by default) for adopter noise management.
"""

from __future__ import annotations

import pytest
from django.db import models

from tenantshield import (
    AuditEventType,
    InMemorySink,
    bind_tenant,
    register_sink,
    tenant_scope,
    unregister_sink,
)
from tenantshield._types import TenantId
from tenantshield.adapters.django import tenant_aware
from tests.integration.django.testapp.models import Invoice


@tenant_aware(audit_cross_tenant_attempts=True)
class AuditedInvoice(models.Model):
    """Tenant-aware model with cross-tenant audit enabled (Finding #1 opt-in)."""

    tenant_id = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = "testapp"


@pytest.fixture
def audit_sink():
    """Register an InMemorySink and yield it; unregister on teardown."""
    sink = InMemorySink()
    register_sink(sink)
    try:
        yield sink
    finally:
        unregister_sink(sink)


@pytest.fixture
def audited_invoices(db, tenant_acme, tenant_globex):  # noqa: ARG001
    """Seed AuditedInvoice rows across acme + globex tenants."""
    with tenant_scope(tenant_acme):
        AuditedInvoice.objects.create(tenant_id="acme", amount=100, description="a1")
        AuditedInvoice.objects.create(tenant_id="acme", amount=200, description="a2")
    with tenant_scope(tenant_globex):
        AuditedInvoice.objects.create(tenant_id="globex", amount=300, description="g1")
        AuditedInvoice.objects.create(tenant_id="globex", amount=400, description="g2")


def _violation_events(sink: InMemorySink) -> list:
    return [e for e in sink.events if e.event_type == AuditEventType.ENFORCEMENT_VIOLATION]


@pytest.mark.django_db
def test_update_emits_violation_when_cross_tenant_pk_targeted(
    audited_invoices,  # noqa: ARG001
    tenant_acme,
    audit_sink,
) -> None:
    """Targeting another tenant's PK via update emits ENFORCEMENT_VIOLATION."""
    globex_pk = AuditedInvoice._unscoped.filter(tenant_id="globex").first().pk  # noqa: SLF001

    with tenant_scope(tenant_acme):
        affected = AuditedInvoice.objects.filter(pk=globex_pk).update(description="hijack")

    assert affected == 0  # SQL filter prevented the write (existing TenantShield contract)

    violations = _violation_events(audit_sink)
    assert len(violations) == 1
    assert violations[0].payload["operation"] == "update"
    assert globex_pk in violations[0].payload["attempted_pks"]


@pytest.mark.django_db
def test_delete_emits_violation_when_cross_tenant_pk_targeted(
    audited_invoices,  # noqa: ARG001
    tenant_acme,
    audit_sink,
) -> None:
    """Targeting another tenant's PK via delete emits ENFORCEMENT_VIOLATION."""
    globex_pk = AuditedInvoice._unscoped.filter(tenant_id="globex").first().pk  # noqa: SLF001

    with tenant_scope(tenant_acme):
        deleted, _ = AuditedInvoice.objects.filter(pk=globex_pk).delete()

    assert deleted == 0  # SQL filter prevented the delete

    violations = _violation_events(audit_sink)
    assert len(violations) == 1
    assert violations[0].payload["operation"] == "delete"
    assert globex_pk in violations[0].payload["attempted_pks"]


@pytest.mark.django_db
def test_legitimate_scoped_update_emits_nothing(
    audited_invoices,  # noqa: ARG001
    tenant_acme,
    audit_sink,
) -> None:
    """Same-tenant update emits no violation event (zero noise)."""
    acme_pk = AuditedInvoice._unscoped.filter(tenant_id="acme").first().pk  # noqa: SLF001

    with tenant_scope(tenant_acme):
        affected = AuditedInvoice.objects.filter(pk=acme_pk).update(description="own-tenant")

    assert affected == 1
    assert _violation_events(audit_sink) == []


@pytest.mark.django_db
def test_legitimate_scoped_delete_emits_nothing(
    audited_invoices,  # noqa: ARG001
    tenant_acme,
    audit_sink,
) -> None:
    """Same-tenant delete emits no violation event."""
    acme_pk = AuditedInvoice._unscoped.filter(tenant_id="acme").first().pk  # noqa: SLF001

    with tenant_scope(tenant_acme):
        deleted, _ = AuditedInvoice.objects.filter(pk=acme_pk).delete()

    assert deleted == 1
    assert _violation_events(audit_sink) == []


@pytest.mark.django_db
def test_audit_disabled_by_default(invoices, tenant_acme, audit_sink) -> None:  # noqa: ARG001
    """The default ``Invoice`` model (no audit flag) emits no violation."""
    globex_pk = Invoice._unscoped.filter(tenant_id="globex").first().pk  # noqa: SLF001

    with tenant_scope(tenant_acme):
        Invoice.objects.filter(pk=globex_pk).update(description="silent-attempt")

    assert _violation_events(audit_sink) == []


@pytest.mark.django_db
def test_audit_payload_contains_attempted_pks(
    audited_invoices,  # noqa: ARG001
    tenant_acme,
    audit_sink,
) -> None:
    """Payload includes ``attempted_pks`` list with the cross-tenant PKs."""
    globex_pks = sorted(
        AuditedInvoice._unscoped.filter(tenant_id="globex").values_list("pk", flat=True)  # noqa: SLF001
    )

    with tenant_scope(tenant_acme):
        AuditedInvoice.objects.filter(pk__in=globex_pks).update(description="bulk-hijack")

    violations = _violation_events(audit_sink)
    assert len(violations) == 1
    assert violations[0].payload["attempted_pks"] == globex_pks


@pytest.mark.django_db
def test_audit_payload_contains_caller_stack_frames(
    audited_invoices,  # noqa: ARG001
    tenant_acme,
    audit_sink,
) -> None:
    """Payload includes ``caller_stack_frames`` for forensic call-site identification."""
    globex_pk = AuditedInvoice._unscoped.filter(tenant_id="globex").first().pk  # noqa: SLF001

    with tenant_scope(tenant_acme):
        AuditedInvoice.objects.filter(pk=globex_pk).update(description="forensic")

    violation = _violation_events(audit_sink)[0]
    frames = violation.payload["caller_stack_frames"]
    assert isinstance(frames, list)
    assert any("test_cross_tenant_audit.py" in str(frame) for frame in frames)


@pytest.mark.django_db
def test_audit_payload_contains_model_qualname_and_operation(
    audited_invoices,  # noqa: ARG001
    tenant_acme,
    audit_sink,
) -> None:
    """Payload includes ``model_qualname`` and ``operation``."""
    globex_pk = AuditedInvoice._unscoped.filter(tenant_id="globex").first().pk  # noqa: SLF001

    with tenant_scope(tenant_acme):
        AuditedInvoice.objects.filter(pk=globex_pk).delete()

    violation = _violation_events(audit_sink)[0]
    assert "AuditedInvoice" in str(violation.payload["model_qualname"])
    assert violation.payload["operation"] == "delete"


@pytest.mark.django_db
def test_audit_tenant_context_captured(
    audited_invoices,  # noqa: ARG001
    tenant_acme,
    audit_sink,
) -> None:
    """When a violation fires inside ``tenant_scope``, the current context is captured."""
    globex_pk = AuditedInvoice._unscoped.filter(tenant_id="globex").first().pk  # noqa: SLF001

    with tenant_scope(tenant_acme):
        AuditedInvoice.objects.filter(pk=globex_pk).update(description="ctx-capture")

    violation = _violation_events(audit_sink)[0]
    assert violation.tenant_context is not None
    assert violation.tenant_context.tenant_id == "acme"


@pytest.mark.django_db
def test_empty_queryset_does_not_emit_violation(
    audited_invoices,  # noqa: ARG001
    tenant_acme,
    audit_sink,
) -> None:
    """Filtering on a PK that does not exist in any tenant emits nothing."""
    nonexistent_pk = 999_999

    with tenant_scope(tenant_acme):
        AuditedInvoice.objects.filter(pk=nonexistent_pk).update(description="nope")

    assert _violation_events(audit_sink) == []


@pytest.mark.django_db
def test_unsafe_unscoped_path_emits_bypass_not_violation(audit_sink) -> None:
    """``_unsafe_unscoped`` writes emit ENFORCEMENT_BYPASS, NOT VIOLATION."""
    AuditedInvoice._unsafe_unscoped.create(  # noqa: SLF001
        tenant_id="acme",
        amount=42,
        description="mode-3-write",
    )

    bypass_events = [
        e for e in audit_sink.events if e.event_type == AuditEventType.ENFORCEMENT_BYPASS
    ]
    violation_events = _violation_events(audit_sink)
    assert len(bypass_events) == 1
    assert violation_events == []


@pytest.mark.django_db
def test_filter_by_non_pk_field_detects_cross_tenant_matches(
    audited_invoices,  # noqa: ARG001
    tenant_acme,  # noqa: ARG001
    audit_sink,
) -> None:
    """Cross-tenant detection works for non-PK filters too (e.g., amount=X)."""
    # Seed one globex row with the same amount as a query target to verify
    # detection works on arbitrary WHERE clauses, not just PK-based.
    ctx = bind_tenant(TenantId("globex"))
    with tenant_scope(ctx):
        AuditedInvoice.objects.create(tenant_id="globex", amount=777, description="g-shared")

    ctx2 = bind_tenant(TenantId("acme"))
    with tenant_scope(ctx2):
        AuditedInvoice.objects.create(tenant_id="acme", amount=777, description="a-shared")

    with tenant_scope(ctx2):
        affected = AuditedInvoice.objects.filter(amount=777).update(description="touched")

    assert affected == 1  # Only acme row was actually updated
    violations = _violation_events(audit_sink)
    # globex row with amount=777 was a cross-tenant match -> emission
    assert len(violations) == 1
    assert violations[0].payload["operation"] == "update"
