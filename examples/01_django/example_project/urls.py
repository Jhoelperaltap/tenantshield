"""Top-level URL routing for the TenantShield example."""

from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("api/", include("example_app.urls")),
]
