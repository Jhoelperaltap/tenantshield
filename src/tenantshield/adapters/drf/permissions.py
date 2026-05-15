"""IsSameTenant DRF permission for tenant isolation enforcement.

Implements the first defense layer of DR-019 (triple defense).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework import permissions

from tenantshield import try_current_tenant

if TYPE_CHECKING:
    from django.db.models import Model
    from rest_framework.request import Request
    from rest_framework.views import APIView


class IsSameTenant(permissions.BasePermission):
    """Permission requiring obj.tenant_id matches active tenant context.

    Two-level enforcement:

    - Request-level (has_permission): requires an active tenant scope.
      Without scope, no operations are permitted regardless of HTTP method.

    - Object-level (has_object_permission): requires obj.tenant_id to
      match the current scope's tenant_id. Applied by DRF on
      retrieve/update/destroy actions for ViewSets that invoke
      check_object_permissions() (standard for ModelViewSet).

    Used in conjunction with TenantContextMiddleware (which establishes
    the scope) and TenantAwareViewSetMixin (which pre-filters the
    queryset). The permission is defense in depth: even if the queryset
    leaks an object from another tenant, the permission denies access.

    Example:
        class InvoiceViewSet(TenantAwareViewSetMixin, ModelViewSet):
            queryset = Invoice.objects.all()
            serializer_class = InvoiceSerializer
            permission_classes = [IsSameTenant]
    """

    message = "Tenant context mismatch."

    def has_permission(self, request: Request, view: APIView) -> bool:  # noqa: ARG002
        """Request-level: require an active tenant scope.

        Returns:
            True if an active tenant scope exists; False otherwise.
        """
        return try_current_tenant() is not None

    def has_object_permission(
        self,
        request: Request,  # noqa: ARG002
        view: APIView,  # noqa: ARG002
        obj: Model,
    ) -> bool:
        """Object-level: obj.tenant_id must match current scope.

        Returns:
            True if obj has tenant_id matching the active scope;
            False otherwise (including when no scope is active or
            obj lacks a tenant_id attribute).
        """
        ctx = try_current_tenant()
        if ctx is None:
            return False
        obj_tenant_id = getattr(obj, "tenant_id", None)
        return obj_tenant_id == ctx.tenant_id
