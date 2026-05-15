"""Integration tests for tenantshield.adapters.drf.

Tests the three layers of DR-019 triple defense independently using
synthetic ViewSets and Serializers. End-to-end integration via
APIClient is in Tarea 2C.A.5 alongside testapp's URL-registered
viewsets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from rest_framework import serializers as drf_serializers
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.viewsets import ModelViewSet

from tenantshield import TenantId, bind_tenant, tenant_scope, try_current_tenant
from tenantshield.adapters.drf import (
    IsSameTenant,
    TenantAwareViewSetMixin,
    TenantPermissionDenied,
    TenantValidatedSerializerMixin,
)
from tenantshield.exceptions import MissingTenantContextError
from tests.integration.django.testapp.models import Invoice

if TYPE_CHECKING:
    from django.db.models import QuerySet


@pytest.fixture
def request_factory():
    return APIRequestFactory()


@pytest.fixture
def acme_scope():
    return tenant_scope(bind_tenant(TenantId("acme")))


@pytest.fixture
def globex_scope():
    return tenant_scope(bind_tenant(TenantId("globex")))


class TestIsSameTenantPermission:
    """Tests for IsSameTenant permission class.

    Validates the first layer of DR-019: request-level + object-level
    enforcement.
    """

    def test_subclass_chain(self):
        assert issubclass(TenantPermissionDenied, DRFPermissionDenied)

    def test_has_permission_no_scope(self, request_factory):
        perm = IsSameTenant()
        req = request_factory.get("/")
        assert perm.has_permission(req, view=None) is False

    def test_has_permission_with_scope(self, request_factory, acme_scope):
        perm = IsSameTenant()
        with acme_scope:
            req = request_factory.get("/")
            assert perm.has_permission(req, view=None) is True

    def test_has_object_permission_matching(self, request_factory, acme_scope):
        class FakeObj:
            def __init__(self, tenant_id):
                self.tenant_id = tenant_id

        perm = IsSameTenant()
        with acme_scope:
            obj = FakeObj("acme")
            assert perm.has_object_permission(request_factory.get("/"), None, obj) is True

    def test_has_object_permission_mismatch(self, request_factory, acme_scope):
        class FakeObj:
            def __init__(self, tenant_id):
                self.tenant_id = tenant_id

        perm = IsSameTenant()
        with acme_scope:
            obj = FakeObj("globex")
            assert perm.has_object_permission(request_factory.get("/"), None, obj) is False

    def test_has_object_permission_no_scope(self, request_factory):
        class FakeObj:
            def __init__(self, tenant_id):
                self.tenant_id = tenant_id

        perm = IsSameTenant()
        obj = FakeObj("acme")
        assert perm.has_object_permission(request_factory.get("/"), None, obj) is False

    def test_has_object_permission_obj_without_tenant_id(self, request_factory, acme_scope):
        class FakeObjNoTenant:
            pass

        perm = IsSameTenant()
        with acme_scope:
            obj = FakeObjNoTenant()
            assert perm.has_object_permission(request_factory.get("/"), None, obj) is False

    def test_exception_carries_context(self):
        exc = TenantPermissionDenied(detail="denial", context={"k": "v"})
        assert dict(exc.context) == {"k": "v"}

    def test_exception_default_detail(self):
        exc = TenantPermissionDenied()
        assert exc.detail is not None
        assert dict(exc.context) == {}


@pytest.mark.django_db
class TestTenantAwareViewSetMixin:
    """Tests for TenantAwareViewSetMixin.

    Validates the second layer of DR-019: queryset-level enforcement.
    Covers Pattern A (manager filtering, mixin idle) and Pattern B
    (mixin enforces, manager bypassed via _base_manager).
    """

    @pytest.fixture(autouse=True)
    def _setup_invoices(self, db, acme_scope, globex_scope):  # noqa: ARG002
        with tenant_scope(bind_tenant(TenantId("acme"))):
            Invoice._base_manager.create(tenant_id="acme", amount=100, description="acme-1")
            Invoice._base_manager.create(tenant_id="acme", amount=200, description="acme-2")
        with tenant_scope(bind_tenant(TenantId("globex"))):
            Invoice._base_manager.create(tenant_id="globex", amount=300, description="globex-1")

    def test_pattern_a_no_scope_manager_raises(self):
        class PatternAViewSet(TenantAwareViewSetMixin, ModelViewSet[Invoice]):
            serializer_class = None

            def get_queryset(self) -> QuerySet[Invoice]:
                return Invoice.objects.all()

        vs = PatternAViewSet()
        with pytest.raises(MissingTenantContextError):
            vs.get_queryset()

    def test_pattern_a_scope_filters_to_tenant(self, acme_scope):
        class PatternAViewSet(TenantAwareViewSetMixin, ModelViewSet[Invoice]):
            serializer_class = None

            def get_queryset(self) -> QuerySet[Invoice]:
                return Invoice.objects.all()

        vs = PatternAViewSet()
        with acme_scope:
            qs = vs.get_queryset()
            descriptions = sorted([inv.description for inv in qs])
            assert qs.count() == 2
            assert descriptions == ["acme-1", "acme-2"]

    def test_pattern_a_multi_tenant_isolation(self, acme_scope, globex_scope):
        class PatternAViewSet(TenantAwareViewSetMixin, ModelViewSet[Invoice]):
            serializer_class = None

            def get_queryset(self) -> QuerySet[Invoice]:
                return Invoice.objects.all()

        vs = PatternAViewSet()
        with acme_scope:
            assert vs.get_queryset().count() == 2
        with globex_scope:
            assert vs.get_queryset().count() == 1

    def test_pattern_b_no_scope_mixin_returns_none(self):
        class PatternBViewSet(TenantAwareViewSetMixin, ModelViewSet[Invoice]):
            queryset = Invoice._base_manager.all()
            serializer_class = None

        vs = PatternBViewSet()
        qs = vs.get_queryset()
        assert qs.count() == 0

    def test_pattern_b_scope_filters_via_mixin(self, acme_scope):
        class PatternBViewSet(TenantAwareViewSetMixin, ModelViewSet[Invoice]):
            queryset = Invoice._base_manager.all()
            serializer_class = None

        vs = PatternBViewSet()
        with acme_scope:
            qs = vs.get_queryset()
            descriptions = sorted([inv.description for inv in qs])
            assert qs.count() == 2
            assert descriptions == ["acme-1", "acme-2"]

    def test_pattern_b_globex_isolation(self, globex_scope):
        class PatternBViewSet(TenantAwareViewSetMixin, ModelViewSet[Invoice]):
            queryset = Invoice._base_manager.all()
            serializer_class = None

        vs = PatternBViewSet()
        with globex_scope:
            qs = vs.get_queryset()
            assert qs.count() == 1
            first = qs.first()
            assert first is not None
            assert first.description == "globex-1"

    def test_scope_cleanup_post_test(self):
        assert try_current_tenant() is None


@pytest.mark.django_db
class TestTenantValidatedSerializerMixin:
    """Tests for TenantValidatedSerializerMixin.

    Validates the third layer of DR-019: write-path enforcement.
    Covers the 3 intervention points: to_internal_value, create, update.
    """

    @pytest.fixture
    def invoice_serializer_cls(self):
        class _InvoiceSerializer(
            TenantValidatedSerializerMixin,
            drf_serializers.ModelSerializer[Invoice],
        ):
            class Meta:
                model = Invoice
                fields: ClassVar[list[str]] = [
                    "id",
                    "tenant_id",
                    "amount",
                    "description",
                ]

        return _InvoiceSerializer

    def test_create_no_scope_raises(self, invoice_serializer_cls):
        serializer = invoice_serializer_cls(
            data={"tenant_id": "acme", "amount": 100, "description": "t"}
        )
        serializer.is_valid(raise_exception=True)
        with pytest.raises(MissingTenantContextError):
            serializer.save()

    def test_create_matching_tenant(self, invoice_serializer_cls, acme_scope):
        with acme_scope:
            serializer = invoice_serializer_cls(
                data={"tenant_id": "acme", "amount": 100, "description": "match"}
            )
            serializer.is_valid(raise_exception=True)
            obj = serializer.save()
            assert obj.tenant_id == "acme"
            assert obj.description == "match"

    def test_create_auto_inject(self, invoice_serializer_cls, acme_scope):
        with acme_scope:
            serializer = invoice_serializer_cls(data={"amount": 200, "description": "autoinject"})
            serializer.is_valid(raise_exception=True)
            obj = serializer.save()
            assert obj.tenant_id == "acme"

    def test_create_mismatch_raises(self, invoice_serializer_cls, acme_scope):
        with acme_scope:
            serializer = invoice_serializer_cls(
                data={"tenant_id": "globex", "amount": 300, "description": "mismatch"}
            )
            serializer.is_valid(raise_exception=True)
            with pytest.raises(TenantPermissionDenied):
                serializer.save()

    def test_update_no_tenant_id_preserves(self, invoice_serializer_cls, acme_scope):
        with acme_scope:
            create_ser = invoice_serializer_cls(
                data={"tenant_id": "acme", "amount": 100, "description": "orig"}
            )
            create_ser.is_valid(raise_exception=True)
            instance = create_ser.save()

            update_ser = invoice_serializer_cls(
                instance=instance,
                data={"amount": 999, "description": "updated"},
                partial=True,
            )
            update_ser.is_valid(raise_exception=True)
            updated = update_ser.save()
            assert updated.tenant_id == "acme"
            assert updated.amount == 999

    def test_update_matching_tenant(self, invoice_serializer_cls, acme_scope):
        with acme_scope:
            create_ser = invoice_serializer_cls(
                data={"tenant_id": "acme", "amount": 100, "description": "orig"}
            )
            create_ser.is_valid(raise_exception=True)
            instance = create_ser.save()

            update_ser = invoice_serializer_cls(
                instance=instance,
                data={"tenant_id": "acme", "amount": 200},
                partial=True,
            )
            update_ser.is_valid(raise_exception=True)
            updated = update_ser.save()
            assert updated.amount == 200

    def test_update_mismatch_raises(self, invoice_serializer_cls, acme_scope):
        with acme_scope:
            create_ser = invoice_serializer_cls(
                data={"tenant_id": "acme", "amount": 100, "description": "orig"}
            )
            create_ser.is_valid(raise_exception=True)
            instance = create_ser.save()

            update_ser = invoice_serializer_cls(
                instance=instance,
                data={"tenant_id": "globex"},
                partial=True,
            )
            update_ser.is_valid(raise_exception=True)
            with pytest.raises(TenantPermissionDenied):
                update_ser.save()

    def test_update_no_scope_raises(self, invoice_serializer_cls, acme_scope):
        with acme_scope:
            create_ser = invoice_serializer_cls(
                data={"tenant_id": "acme", "amount": 100, "description": "orig"}
            )
            create_ser.is_valid(raise_exception=True)
            instance = create_ser.save()

        update_ser = invoice_serializer_cls(
            instance=instance,
            data={"amount": 200},
            partial=True,
        )
        update_ser.is_valid(raise_exception=True)
        with pytest.raises(MissingTenantContextError):
            update_ser.save()


@pytest.mark.django_db(transaction=True)
class TestDRFIntegrationEndToEnd:
    """End-to-end DRF integration tests via APIClient.

    Exercises the full stack: HTTP request -> TenantContextMiddleware
    extracts tenant from X-Tenant-Id header -> IsSameTenant permission
    -> TenantAwareViewSetMixin filters queryset ->
    TenantValidatedSerializerMixin validates writes -> DRF response.

    Requires testapp/viewsets.py InvoiceViewSet registered at
    /api/invoices/ (testapp/urls.py via DefaultRouter).
    """

    @pytest.fixture
    def api_client(self):
        client = APIClient()
        # Disable raise so middleware exceptions become 500 responses
        # rather than propagating out of the test (Rule 42 / E40).
        client.raise_request_exception = False
        return client

    @pytest.fixture(autouse=True)
    def _setup_invoices(self, acme_scope, globex_scope):
        with acme_scope:
            Invoice._base_manager.create(tenant_id="acme", amount=100, description="acme-e2e-1")
            Invoice._base_manager.create(tenant_id="acme", amount=200, description="acme-e2e-2")
        with globex_scope:
            Invoice._base_manager.create(tenant_id="globex", amount=300, description="globex-e2e-1")

    def test_list_invoices_acme_returns_2(self, api_client):
        response = api_client.get("/api/invoices/", HTTP_X_TENANT_ID="acme")
        assert response.status_code == 200
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        assert len(results) == 2
        descriptions = sorted([r["description"] for r in results])
        assert descriptions == ["acme-e2e-1", "acme-e2e-2"]

    def test_list_invoices_globex_returns_1(self, api_client):
        response = api_client.get("/api/invoices/", HTTP_X_TENANT_ID="globex")
        assert response.status_code == 200
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        assert len(results) == 1
        assert results[0]["description"] == "globex-e2e-1"

    def test_retrieve_cross_tenant_returns_404(self, api_client):
        with tenant_scope(bind_tenant(TenantId("acme"))):
            acme_invoice = Invoice.objects.get(description="acme-e2e-1")

        response = api_client.get(
            f"/api/invoices/{acme_invoice.pk}/",
            HTTP_X_TENANT_ID="globex",
        )
        assert response.status_code == 404

    def test_create_invoice_acme(self, api_client):
        response = api_client.post(
            "/api/invoices/",
            data={"amount": 999, "description": "created-via-api"},
            HTTP_X_TENANT_ID="acme",
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert body["tenant_id"] == "acme"
        assert body["description"] == "created-via-api"

    def test_create_invoice_cross_tenant_returns_403(self, api_client):
        response = api_client.post(
            "/api/invoices/",
            data={"tenant_id": "globex", "amount": 500, "description": "should-fail"},
            HTTP_X_TENANT_ID="acme",
            format="json",
        )
        assert response.status_code == 403

    def test_request_no_tenant_header_returns_error(self, api_client):
        response = api_client.get("/api/invoices/")
        assert response.status_code in (401, 403, 404, 500)
