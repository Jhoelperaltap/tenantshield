"""TenantValidatedSerializerMixin for DRF write-path enforcement.

Implements the third defense layer of DR-019 (triple defense).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from tenantshield import try_current_tenant
from tenantshield.adapters.drf.exceptions import TenantPermissionDenied
from tenantshield.exceptions import MissingTenantContextError

if TYPE_CHECKING:
    from django.db.models import Model


class TenantValidatedSerializerMixin:
    """Mixin validating tenant_id on DRF serializer write operations.

    One of the three independent enforcement layers documented in DR-019
    (Sub-phase 2C). The mixin acts at write-time, BEFORE ``save()`` is
    invoked on the model instance.

    Relationship to Phase 2A signal enforcement:
    Phase 2A.8 installs ``pre_save`` and ``pre_delete`` signal handlers
    on ``@tenant_aware`` models that enforce tenant coherence at save
    time. The serializer mixin does NOT replace this enforcement; it
    complements it by:

    1. Raising ``TenantPermissionDenied`` (HTTP 403 via DRF default
       exception handler) instead of ``MissingTenantContextError``
       (HTTP 500). DRF-friendly UX.
    2. Catching mismatches BEFORE database access, avoiding partial
       transactions or wasted query overhead.
    3. Auto-injecting ``tenant_id`` from active scope when absent in
       raw input data, allowing clients to omit it from request payload
       without triggering DRF's ``required=True`` field validation.

    Three intervention points:

    1. ``to_internal_value`` (pre-validation): if raw input data lacks
       ``tenant_id`` AND an active tenant scope exists, inject
       ``tenant_id`` from the scope into the data. This avoids DRF's
       ``required=True`` default rejecting the request before the
       mixin can act.

    2. ``create`` (post-validation): validates that
       ``validated_data['tenant_id']`` matches the active scope. Raises
       ``TenantPermissionDenied`` on mismatch.

    3. ``update`` (post-validation): validates that an explicitly
       provided ``validated_data['tenant_id']`` matches the active
       scope. Does NOT auto-inject; partial updates preserve the
       instance's existing tenant_id.

    Behavior matrix:

    +-----------+----------+-------------------+--------------------------------+
    | Operation | Scope    | Payload tenant_id | Result                         |
    +===========+==========+===================+================================+
    | create    | None     | any               | MissingTenantContextError      |
    +-----------+----------+-------------------+--------------------------------+
    | create    | acme     | absent            | injected as 'acme', proceeds   |
    +-----------+----------+-------------------+--------------------------------+
    | create    | acme     | 'acme'            | proceeds                       |
    +-----------+----------+-------------------+--------------------------------+
    | create    | acme     | 'globex'          | TenantPermissionDenied         |
    +-----------+----------+-------------------+--------------------------------+
    | update    | None     | any               | MissingTenantContextError      |
    +-----------+----------+-------------------+--------------------------------+
    | update    | acme     | absent            | proceeds, tenant_id unchanged  |
    +-----------+----------+-------------------+--------------------------------+
    | update    | acme     | 'acme'            | proceeds                       |
    +-----------+----------+-------------------+--------------------------------+
    | update    | acme     | 'globex'          | TenantPermissionDenied         |
    +-----------+----------+-------------------+--------------------------------+

    MRO note: like ``TenantAwareViewSetMixin``, this mixin's
    ``to_internal_value``, ``create`` and ``update`` are shadowed if a
    subclass defines them without ``super()`` delegation. Recommended
    pattern: do NOT override these methods in your serializer subclass;
    let DRF's ``ModelSerializer`` provide them and this mixin wrap
    them.

    User pattern (no boilerplate needed):

        class InvoiceSerializer(TenantValidatedSerializerMixin,
                                serializers.ModelSerializer):
            class Meta:
                model = Invoice
                fields = ['id', 'tenant_id', 'amount', 'description']

    The mixin handles ``required=True`` tenant_id transparently via
    ``to_internal_value``. No need to declare
    ``tenant_id = CharField(required=False)``.

    Compatible with:
    - ``ModelSerializer``, ``Serializer``, ``HyperlinkedModelSerializer``.
    - Custom serializers exposing ``create()`` / ``update()`` per DRF
      contract.

    Should be placed FIRST in the MRO chain.
    """

    def to_internal_value(self, data: Any) -> dict[str, Any]:  # noqa: ANN401
        """Pre-validation hook: inject tenant_id from active scope if
        absent, so DRF's required validation passes naturally.

        If ``tenant_id`` is already present in raw data, leave it
        untouched so that mismatch detection in ``create()`` /
        ``update()`` can fire ``TenantPermissionDenied`` against the
        incoming value.

        Note on typing: ``data: Any`` matches the DRF parent contract.
        ``drf-stubs`` declares ``Field.to_internal_value(self, data: _DT)
        -> _VT`` and ``BaseSerializer(Field[Any, Any, Any, _IN])``
        parametrizes both type variables as ``Any``. Narrowing the
        parameter type in this override would violate Liskov
        substitution against the upstream contract. The localized
        ``# noqa: ANN401`` on the signature documents that this is
        ``Any`` by upstream contract, not by laziness.
        """
        ctx = try_current_tenant()
        if ctx is not None and "tenant_id" not in data:
            data = dict(data)
            data["tenant_id"] = str(ctx.tenant_id)
        return cast("dict[str, Any]", super().to_internal_value(data))  # type: ignore[misc]

    def create(self, validated_data: dict[str, Any]) -> Model:
        """Create model instance after validating tenant_id match.

        At this point ``tenant_id`` is always present in ``validated_data``
        because either the client sent it or ``to_internal_value``
        injected it.

        Raises:
            MissingTenantContextError: if no active tenant scope.
            TenantPermissionDenied: if validated_data['tenant_id'] does
                not match active scope.
        """
        ctx = try_current_tenant()
        if ctx is None:
            raise MissingTenantContextError(operation="serializer.create")

        incoming_tenant = validated_data.get("tenant_id")
        if incoming_tenant is not None and incoming_tenant != ctx.tenant_id:
            raise TenantPermissionDenied(
                detail=(
                    f"Cannot create object for tenant {incoming_tenant!r} "
                    f"under active context {ctx.tenant_id!r}."
                ),
                context={
                    "operation": "serializer.create",
                    "incoming_tenant": str(incoming_tenant),
                    "active_tenant": str(ctx.tenant_id),
                },
            )
        return cast("Model", super().create(validated_data))  # type: ignore[misc]

    def update(
        self,
        instance: Model,
        validated_data: dict[str, Any],
    ) -> Model:
        """Update model instance with tenant_id mismatch rejection.

        Unlike ``create``, this method does NOT auto-inject ``tenant_id``;
        partial updates legitimately omit it, and the instance's
        existing value is preserved.

        Raises:
            MissingTenantContextError: if no active tenant scope.
            TenantPermissionDenied: if validated_data['tenant_id'] is
                explicitly provided and does not match active scope
                (prevents tenant reassignment).
        """
        ctx = try_current_tenant()
        if ctx is None:
            raise MissingTenantContextError(operation="serializer.update")

        incoming_tenant = validated_data.get("tenant_id")
        if incoming_tenant is not None and incoming_tenant != ctx.tenant_id:
            raise TenantPermissionDenied(
                detail=(
                    f"Cannot reassign object to tenant {incoming_tenant!r} "
                    f"under active context {ctx.tenant_id!r}."
                ),
                context={
                    "operation": "serializer.update",
                    "incoming_tenant": str(incoming_tenant),
                    "active_tenant": str(ctx.tenant_id),
                    "instance_pk": instance.pk,
                },
            )
        return cast("Model", super().update(instance, validated_data))  # type: ignore[misc]
