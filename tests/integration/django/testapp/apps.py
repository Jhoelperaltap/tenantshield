"""Test app for integration tests."""

from django.apps import AppConfig


class TestAppConfig(AppConfig):
    name = "tests.integration.django.testapp"
    label = "testapp"
    default_auto_field = "django.db.models.BigAutoField"
