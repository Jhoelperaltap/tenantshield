"""App config for example_app."""

from __future__ import annotations

from django.apps import AppConfig


class ExampleAppConfig(AppConfig):
    """TenantShield demo application."""

    name = "example_app"
    default_auto_field = "django.db.models.BigAutoField"
