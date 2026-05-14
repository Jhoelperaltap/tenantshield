"""Internal type aliases for TenantShield.

This module is private; consumers should import re-exported names from the
top-level ``tenantshield`` package or from ``tenantshield.context``.
"""

from __future__ import annotations

from typing import NewType

TenantId = NewType("TenantId", str)
"""Identifier for a tenant.

A ``NewType`` over ``str``. At runtime it is exactly ``str``; the wrapper
exists only to give type checkers a way to distinguish tenant identifiers
from arbitrary strings. Construct with ``TenantId("acme")`` (or
``TenantId(str(value))`` when coercing from non-string sources).

Equality is by string value. No normalization (case folding, trimming) is
applied; callers are responsible for normalizing at the system boundary.
"""

__all__ = ["TenantId"]
