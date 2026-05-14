"""pytest-django configuration for integration tests."""

from __future__ import annotations

import os

import django
from django.conf import settings


def pytest_configure(config: object) -> None:  # noqa: ARG001
    """Configure Django before tests run."""
    if not settings.configured:
        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE",
            "tests.integration.django.settings",
        )
        django.setup()
