"""Exception types re-exported for the SQLAlchemy adapter.

Re-exports core tenant context exceptions. SA-specific exception types
may be added later if architectural need emerges (see
``PHASE_3A_KICKOFF.md`` sec 2 -- "Possibly new ``SqlAlchemyTenantError``
if SA-specific context needed"). The deferral is empirical-driven: new
exception types are added when implementation evidence justifies them
(per DR-019 reformulation lesson from Sub-fase 2C).
"""

from __future__ import annotations

from tenantshield.exceptions import (
    CrossTenantAccessError,
    MissingTenantContextError,
)

__all__ = [
    "CrossTenantAccessError",
    "MissingTenantContextError",
]
