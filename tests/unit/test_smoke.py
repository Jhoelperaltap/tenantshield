"""Smoke tests verifying the package imports and exposes its version."""

from __future__ import annotations

import re

import tenantshield


def test_package_imports() -> None:
    assert tenantshield is not None


def test_version_is_pep440() -> None:
    assert re.match(r"^\d+\.\d+\.\d+(a|b|rc)?\d*$", tenantshield.__version__)


def test_public_api_is_explicit() -> None:
    assert hasattr(tenantshield, "__all__")
    assert "__version__" in tenantshield.__all__
