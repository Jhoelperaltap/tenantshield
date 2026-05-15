"""System checks for TenantShield Django adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from django.conf import settings
from django.core.checks import Error, Warning  # noqa: A004 -- Django's Warning, not builtin

from tenantshield.registry import default_registry

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from django.db.models import Model

_MIDDLEWARE_PATH_SHORT = "tenantshield.adapters.django.TenantContextMiddleware"
_MIDDLEWARE_PATH_FULL = "tenantshield.adapters.django.middleware.TenantContextMiddleware"


def _middleware_is_installed() -> bool:
    """Return True when TenantContextMiddleware is in settings.MIDDLEWARE."""
    installed = list(getattr(settings, "MIDDLEWARE", []))
    return _MIDDLEWARE_PATH_SHORT in installed or _MIDDLEWARE_PATH_FULL in installed


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


def check_middleware_strategy_configured(
    app_configs: Sequence[Any] | None = None,  # noqa: ARG001
    **kwargs: object,  # noqa: ARG001
) -> list[Error]:
    """E002: Error when TenantContextMiddleware installed but no strategy configured.

    The middleware requires settings.TENANTSHIELD['tenant_extraction'] to
    be set. Detecting this misconfiguration at ``python manage.py check``
    time prevents broken deployments where the middleware would raise
    ImproperlyConfigured at first-request time.
    """
    errors: list[Error] = []
    if not _middleware_is_installed():
        return errors  # Middleware not installed; no E002 to raise.

    raw_config: object = getattr(settings, "TENANTSHIELD", None) or {}
    if not isinstance(raw_config, Mapping):
        errors.append(
            Error(
                f"settings.TENANTSHIELD must be a dict (got {type(raw_config).__name__}).",
                hint=(
                    "Set TENANTSHIELD = {'tenant_extraction': 'subdomain'} "
                    "or another valid strategy."
                ),
                id="tenantshield.E002",
            ),
        )
        return errors

    config = cast("Mapping[str, object]", raw_config)
    if config.get("tenant_extraction") is None:
        errors.append(
            Error(
                "TenantContextMiddleware is installed but "
                "settings.TENANTSHIELD['tenant_extraction'] is not configured.",
                hint=(
                    "Set TENANTSHIELD['tenant_extraction'] to 'subdomain', "
                    "'header', 'jwt', or a callable. See DR-016 for details."
                ),
                id="tenantshield.E002",
            ),
        )

    return errors


def check_public_tenant_mode_visible(
    app_configs: Sequence[Any] | None = None,  # noqa: ARG001
    **kwargs: object,  # noqa: ARG001
) -> list[Warning]:
    """W001: Warning when ``on_missing_tenant='public'`` is configured.

    The ``public`` mode binds a reserved ``__public__`` tenant when
    extraction fails. This is intentional bypass and operators should be
    aware that requests without tenant context are not rejected.
    """
    warnings: list[Warning] = []
    raw_config: object = getattr(settings, "TENANTSHIELD", None) or {}
    if not isinstance(raw_config, Mapping):
        return warnings  # E002 path handles non-dict settings.

    config = cast("Mapping[str, object]", raw_config)
    if config.get("on_missing_tenant") == "public":
        warnings.append(
            Warning(
                "TENANTSHIELD['on_missing_tenant']='public' is configured. "
                "Requests without an extractable tenant will bind the "
                "reserved __public__ tenant and proceed.",
                hint=(
                    "If this is intentional (mixed public + tenant APIs), "
                    "ignore this warning. Otherwise, set on_missing_tenant "
                    "to 'raise', '404', or a callable."
                ),
                id="tenantshield.W001",
            ),
        )

    return warnings


def check_middleware_installed_for_tenant_aware_models(
    app_configs: Sequence[Any] | None = None,  # noqa: ARG001
    **kwargs: object,  # noqa: ARG001
) -> list[Warning]:
    """W002: Warning when @tenant_aware models exist but middleware not installed.

    Programmatic usage (Celery workers, management commands, scripts) is
    legitimate, so this is a Warning, not an Error. Operators that serve
    HTTP traffic must ensure the middleware is in MIDDLEWARE.
    """
    warnings: list[Warning] = []
    if not list(default_registry):
        return warnings  # No registered models; nothing to warn about.

    if _middleware_is_installed():
        return warnings  # Middleware installed; W002 does not apply.

    warnings.append(
        Warning(
            "@tenant_aware models are registered but TenantContextMiddleware is not in MIDDLEWARE.",
            hint=(
                "If you serve HTTP traffic with these models, add "
                "'tenantshield.adapters.django.TenantContextMiddleware' "
                "to MIDDLEWARE. For programmatic usage only (Celery, "
                "scripts), this warning can be safely ignored."
            ),
            id="tenantshield.W002",
        ),
    )

    return warnings
