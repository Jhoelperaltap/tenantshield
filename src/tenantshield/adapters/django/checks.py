"""System checks for TenantShield Django adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.core.checks import Error

from tenantshield.registry import default_registry

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from django.db.models import Model


# Django's system check framework invokes registered callables with positional
# and keyword args (app_configs, databases, ...). The signature below is
# required by that contract even when the implementation ignores the inputs.
def check_tenant_aware_models_have_tenant_field(
    app_configs: Sequence[Any] | None = None,  # noqa: ARG001
    **kwargs: object,  # noqa: ARG001
) -> list[Error]:
    """Verify every @tenant_aware model has the declared tenant field.

    Catches the bug where a user decorates a model but forgets to declare
    the tenant_id field (or declares it with a different name than the
    configured tenant_field).
    """
    errors: list[Error] = []
    for entry in default_registry:
        model = entry.model
        # Only check Django models; the registry may contain non-Django classes
        # in test scenarios.
        if not hasattr(model, "_meta"):
            continue
        # model._meta is Django's documented introspection API (public by contract).
        # Cast narrows from `type` (generic registry entry) to `type[Model]` so the
        # django-stubs typing of _meta and get_fields is visible to pyright.
        django_model = cast("type[Model]", model)
        field_names = {f.name for f in django_model._meta.get_fields()}  # noqa: SLF001
        if entry.tenant_field not in field_names:
            errors.append(
                Error(
                    f"Model {model.__qualname__!r} is registered as tenant-aware "
                    f"but has no field named {entry.tenant_field!r}.",
                    hint=(
                        f"Add a field named {entry.tenant_field!r} to the model, "
                        f"or pass tenant_field=... to @tenant_aware."
                    ),
                    obj=model,
                    id="tenantshield.E001",
                ),
            )
    return errors
