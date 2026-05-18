"""TenantShield observability configuration.

Sub-fase 5B.1 -- disabled-default emission control per Decision 6-A.

Adopters explicitly enable via ``configure(emit_events=True)``. Disabled default
preserves Phase 4 adopter zero log volume change. Disabled-default gate
overhead ~6 ns/call empirically validated en Sub-fase 5B.0 Scenario #3;
adding the ``is_enabled()`` function-call indirection keeps the hot path
under the <100 ns acceptance threshold ratified there.
"""

_observability_enabled: bool = False


def configure(*, emit_events: bool = False) -> None:
    """Configure TenantShield observability emission.

    Args:
        emit_events: If ``True``, enables structured event emission via
            structlog logger ``tenantshield.observability``. Default
            ``False`` preserves zero log volume.

    Note:
        Audit logger ``tenantshield.audit`` operates independently of this
        configuration -- security-critical events always route via audit
        logger regardless of observability emission state (Decision 7-A).
    """
    global _observability_enabled  # noqa: PLW0603 -- module-level toggle is the canonical adopter-facing configure() pattern; mutable state intentionally module-scoped to preserve the disabled-default hot path measured at ~6 ns/call in Sub-fase 5B.0 Scenario #3.
    _observability_enabled = emit_events


def is_enabled() -> bool:
    """Return current observability emission state.

    Returns:
        ``True`` if observability emission is enabled via ``configure``,
        ``False`` otherwise.
    """
    return _observability_enabled
