"""Tests for tenantshield.exceptions."""

from __future__ import annotations

import pytest

from tenantshield._types import TenantId
from tenantshield.exceptions import (
    AdapterError,
    AmbiguousTenantContextError,
    ConfigurationError,
    CrossTenantAccessError,
    CrossTenantJoinError,
    EnforcementError,
    MissingTenantContextError,
    TenantContextError,
    TenantShieldError,
    UnscopedQueryError,
)


class TestHierarchy:
    """Verify the inheritance tree matches the specification."""

    def test_all_subclass_tenantshield_error(self) -> None:
        for exc_type in (
            ConfigurationError,
            TenantContextError,
            EnforcementError,
            AdapterError,
            MissingTenantContextError,
            AmbiguousTenantContextError,
            CrossTenantAccessError,
            UnscopedQueryError,
            CrossTenantJoinError,
        ):
            assert issubclass(exc_type, TenantShieldError)

    def test_context_errors_subclass_tenant_context_error(self) -> None:
        assert issubclass(MissingTenantContextError, TenantContextError)
        assert issubclass(AmbiguousTenantContextError, TenantContextError)

    def test_enforcement_errors_subclass_enforcement_error(self) -> None:
        assert issubclass(CrossTenantAccessError, EnforcementError)
        assert issubclass(UnscopedQueryError, EnforcementError)
        assert issubclass(CrossTenantJoinError, EnforcementError)


class TestMissingTenantContextError:
    def test_message_includes_operation(self) -> None:
        exc = MissingTenantContextError(operation="read")
        assert "read" in str(exc)

    def test_to_dict_round_trip(self) -> None:
        exc = MissingTenantContextError(
            operation="read",
            stack_context={"file": "x.py"},
        )
        d = exc.to_dict()
        assert d["type"] == "MissingTenantContextError"
        assert d["operation"] == "read"
        assert d["stack_context"] == {"file": "x.py"}

    def test_can_raise_and_catch(self) -> None:
        with pytest.raises(MissingTenantContextError):
            raise MissingTenantContextError(operation="write")


class TestAmbiguousTenantContextError:
    def test_message_includes_both_tenants(self) -> None:
        exc = AmbiguousTenantContextError(
            tenant_id_outer=TenantId("alpha"),
            tenant_id_inner=TenantId("beta"),
        )
        assert "alpha" in str(exc)
        assert "beta" in str(exc)

    def test_to_dict_round_trip(self) -> None:
        exc = AmbiguousTenantContextError(
            tenant_id_outer=TenantId("alpha"),
            tenant_id_inner=TenantId("beta"),
            stack_context={"depth": 2},
        )
        d = exc.to_dict()
        assert d["type"] == "AmbiguousTenantContextError"
        assert d["tenant_id_outer"] == "alpha"
        assert d["tenant_id_inner"] == "beta"
        assert d["stack_context"] == {"depth": 2}

    def test_can_raise_and_catch(self) -> None:
        with pytest.raises(AmbiguousTenantContextError):
            raise AmbiguousTenantContextError(
                tenant_id_outer=TenantId("a"),
                tenant_id_inner=TenantId("b"),
            )


class TestCrossTenantAccessError:
    def test_message_includes_model_and_operation(self) -> None:
        exc = CrossTenantAccessError(
            tenant_id_expected=TenantId("alpha"),
            tenant_id_actual=TenantId("beta"),
            model="User",
            operation="select",
        )
        assert "User" in str(exc)
        assert "select" in str(exc)

    def test_to_dict_round_trip(self) -> None:
        exc = CrossTenantAccessError(
            tenant_id_expected=TenantId("alpha"),
            tenant_id_actual=TenantId("beta"),
            model="User",
            operation="select",
            stack_context={"query_id": 42},
        )
        d = exc.to_dict()
        assert d["type"] == "CrossTenantAccessError"
        assert d["tenant_id_expected"] == "alpha"
        assert d["tenant_id_actual"] == "beta"
        assert d["model"] == "User"
        assert d["operation"] == "select"
        assert d["stack_context"] == {"query_id": 42}

    def test_none_fields_serialize_as_none(self) -> None:
        exc = CrossTenantAccessError(
            tenant_id_expected=None,
            tenant_id_actual=None,
            model=None,
            operation="select",
        )
        d = exc.to_dict()
        assert d["tenant_id_expected"] is None
        assert d["tenant_id_actual"] is None
        assert d["model"] is None

    def test_can_raise_and_catch(self) -> None:
        with pytest.raises(CrossTenantAccessError):
            raise CrossTenantAccessError(
                tenant_id_expected=TenantId("a"),
                tenant_id_actual=TenantId("b"),
                model="X",
                operation="op",
            )


class TestUnscopedQueryError:
    def test_message_includes_model_and_operation(self) -> None:
        exc = UnscopedQueryError(model="User", operation="list")
        assert "User" in str(exc)
        assert "list" in str(exc)

    def test_to_dict_round_trip(self) -> None:
        exc = UnscopedQueryError(
            model="User",
            operation="list",
            stack_context={"path": "/api/users"},
        )
        d = exc.to_dict()
        assert d["type"] == "UnscopedQueryError"
        assert d["model"] == "User"
        assert d["operation"] == "list"
        assert d["stack_context"] == {"path": "/api/users"}

    def test_can_raise_and_catch(self) -> None:
        with pytest.raises(UnscopedQueryError):
            raise UnscopedQueryError(model="X", operation="op")


class TestCrossTenantJoinError:
    def test_message_includes_both_models(self) -> None:
        exc = CrossTenantJoinError(
            tenant_id_expected=TenantId("alpha"),
            model_left="User",
            model_right="Order",
        )
        assert "User" in str(exc)
        assert "Order" in str(exc)

    def test_to_dict_round_trip(self) -> None:
        exc = CrossTenantJoinError(
            tenant_id_expected=TenantId("alpha"),
            model_left="User",
            model_right="Order",
            stack_context={"join_kind": "inner"},
        )
        d = exc.to_dict()
        assert d["type"] == "CrossTenantJoinError"
        assert d["tenant_id_expected"] == "alpha"
        assert d["model_left"] == "User"
        assert d["model_right"] == "Order"
        assert d["stack_context"] == {"join_kind": "inner"}

    def test_can_raise_and_catch(self) -> None:
        with pytest.raises(CrossTenantJoinError):
            raise CrossTenantJoinError(
                tenant_id_expected=TenantId("a"),
                model_left="X",
                model_right="Y",
            )


class TestPlainErrors:
    """Intermediate errors without structured fields."""

    @pytest.mark.parametrize(
        "exc_type",
        [
            ConfigurationError,
            TenantContextError,
            EnforcementError,
            AdapterError,
            TenantShieldError,
        ],
    )
    def test_accepts_string_message(self, exc_type: type[Exception]) -> None:
        exc = exc_type("something went wrong")
        assert "something went wrong" in str(exc)
