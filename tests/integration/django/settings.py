"""Minimal Django settings for TenantShield integration tests."""

SECRET_KEY = "test-secret-not-for-production"  # noqa: S105

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "tenantshield.adapters.django",
    "tests.integration.django.testapp",
]

MIDDLEWARE: list[str] = []

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
