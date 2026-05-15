"""Django settings for the TenantShield example.

This is a demonstration project, NOT a production deployment template.
Many settings are simplified for clarity at the cost of production
safety.
"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: this SECRET_KEY is FOR DEMO ONLY.
# Generate a new SECRET_KEY for any non-demo deployment.
# See: https://docs.djangoproject.com/en/stable/topics/signing/
SECRET_KEY = "django-insecure-tenantshield-demo-only-do-not-use-in-production"  # noqa: S105

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]  # Demo only; restrict in production.

# Application definition

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "example_app",
]

MIDDLEWARE = [
    "tenantshield.adapters.django.TenantContextMiddleware",
]

TENANTSHIELD = {
    "tenant_extraction": "header",
    "header_name": "X-Tenant-Id",
    "on_missing_tenant": "raise",
}

ROOT_URLCONF = "example_project.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True

# Logging: keep simple for demo. Production deployments should use
# structured logging via TenantShield's audit bus (TODO Phase 4+).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
