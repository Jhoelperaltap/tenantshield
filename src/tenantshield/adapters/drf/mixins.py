"""TenantAwareViewSetMixin for DRF ViewSets.

Implements the second defense layer of DR-019 (triple defense).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from tenantshield import try_current_tenant

if TYPE_CHECKING:
    from django.db.models import QuerySet


class TenantAwareViewSetMixin:
    """Mixin enforcing tenant isolation at the ViewSet queryset level.

    One of the three independent enforcement layers documented in DR-019
    (Sub-phase 2C). The three layers act at different points of the DRF
    request lifecycle, NOT as composable filters on a single queryset:

    1. ``IsSameTenant`` permission: rejects at request/object level
       BEFORE the queryset is evaluated.
    2. ``TenantAwareViewSetMixin`` (this class): filters at queryset
       level WHEN the underlying queryset is NOT protected by an
       ``@tenant_aware`` manager.
    3. ``TenantValidatedSerializerMixin``: validates writes BEFORE
       ``save()``.

    The mixin is an **alternative** enforcement to the ``@tenant_aware``
    manager, NOT a redundant filter applied on top of it. Python MRO
    means that if a subclass defines ``get_queryset()`` directly, the
    mixin's ``get_queryset()`` is shadowed and never executes. To engage
    the mixin, the ViewSet must either:

    - NOT define ``get_queryset()`` (mixin inherited), OR
    - Define ``get_queryset()`` that calls ``super().get_queryset()``
      to delegate to the mixin.

    Recommended usage patterns:

    **Pattern A -- Model with @tenant_aware (manager filters, mixin idle):**

        class InvoiceViewSet(TenantAwareViewSetMixin, ModelViewSet):
            serializer_class = InvoiceSerializer
            permission_classes = [IsSameTenant]

            def get_queryset(self):
                return Invoice.objects.all()  # @tenant_aware manager filters

        The mixin is present as a guard but does not engage; the
        manager's ``TenantAwareManager`` enforces tenant isolation. The
        mixin becomes relevant if the model loses ``@tenant_aware``
        registration in the future.

    **Pattern B -- Model without @tenant_aware or _base_manager bypass:**

        class LegacyInvoiceViewSet(TenantAwareViewSetMixin, ModelViewSet):
            queryset = LegacyInvoice._base_manager.all()  # no @tenant_aware
            serializer_class = LegacyInvoiceSerializer
            permission_classes = [IsSameTenant]

        No ``get_queryset()`` override -> mixin's ``get_queryset()`` is
        the sole enforcement. Filters by ``tenant_id`` via ``filter()``
        on the queryset.

    **Anti-pattern -- queryset as class attribute with @tenant_aware:**

        # BROKEN: evaluated at class load time, fails with
        # MissingTenantContextError because no scope is active.
        class InvoiceViewSet(TenantAwareViewSetMixin, ModelViewSet):
            queryset = Invoice.objects.all()  # raises at class body eval

    Behavior summary:

    - With active tenant scope: returns
      ``super().get_queryset().filter(tenant_id=ctx.tenant_id)``.
      Engages only if the subclass does not shadow ``get_queryset()``.
    - Without active tenant scope: returns
      ``super().get_queryset().none()``. Falls back to the underlying
      queryset's empty form rather than raising; raising would
      short-circuit DRF's response generation.

    Compatible with:
    - ``ModelViewSet``, ``ReadOnlyModelViewSet``, ``GenericViewSet``.
    - Any DRF view exposing ``get_queryset()`` per DRF contract.

    Should be placed FIRST in the MRO chain.
    """

    def get_queryset(self) -> QuerySet[Any]:
        """Return queryset filtered to active tenant scope.

        Returns empty queryset (``.none()``) if no scope is active.
        """
        queryset = cast("QuerySet[Any]", super().get_queryset())  # type: ignore[misc]
        ctx = try_current_tenant()
        if ctx is None:
            return queryset.none()
        return queryset.filter(tenant_id=ctx.tenant_id)
