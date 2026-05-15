"""Minimal Django settings for TenantShield integration tests."""

SECRET_KEY = "test-secret-not-for-production"  # noqa: S105

DEBUG = False

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "tenantshield.adapters.django",
    "tests.integration.django.testapp",
]

ROOT_URLCONF = "tests.integration.django.testapp.urls"

MIDDLEWARE = [
    "tenantshield.adapters.django.TenantContextMiddleware",
]

TENANTSHIELD = {
    "tenant_extraction": "header",
    "header_name": "X-Tenant-Id",
    "on_missing_tenant": "raise",
}

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
