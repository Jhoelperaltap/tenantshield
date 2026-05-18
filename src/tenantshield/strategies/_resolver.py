"""Cross-adapter ``resolve_strategy()`` factory.

Per Decision 4-A from the Phase 4 kickoff: framework-agnostic strategy
factory lives en the top-level ``tenantshield.strategies`` module.
Adapters re-export for adopter ergonomics (Decision 5-B SA adapter
re-exports; Django adapter retains its own ``resolve_strategy`` with
Phase 2B ``ImproperlyConfigured`` semantics post-DPRJ-2 housekeeping).

Configuration schema
--------------------

::

    {
        "tenant_extraction": "header" | "host" | "jwt" | callable,
        "header_name": str,        # optional, for "header"
        "jwt_secret": str,         # required, for "jwt"
        "jwt_claim": str,          # optional, default "tenant_id"
        "jwt_algorithm": str,      # optional, default "HS256"
    }

Error model
-----------

Misconfiguration raises ``ValueError``. Adapter shims may translate
to adapter-canonical exception classes (e.g., the Django adapter's
``resolve_strategy`` raises ``django.core.exceptions.ImproperlyConfigured``
per Phase 2B / DPRJ-2 contract). The core factory uses the Python
stdlib idiom; SA adopters using the core factory directly receive
``ValueError``.

Note: ``"subdomain"`` (Phase 2B Django-specific extraction key) is not
recognized by the core factory; cross-adapter equivalent is ``"host"``
which dispatches to ``HostStrategy`` (Decision 5-B). Django adopters
using ``"subdomain"`` continue via the Django adapter's
``resolve_strategy``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield.strategies.callable_ import CallableStrategy
from tenantshield.strategies.header import HeaderStrategy
from tenantshield.strategies.host import HostStrategy
from tenantshield.strategies.jwt import JWTStrategy

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tenantshield.strategies.base import TenantExtractionStrategy


def resolve_strategy(config: Mapping[str, object]) -> TenantExtractionStrategy:
    """Construct a cross-adapter strategy from configuration mapping.

    Examples::

        resolve_strategy({"tenant_extraction": "header"})
        resolve_strategy({"tenant_extraction": "header", "header_name": "X-Org"})
        resolve_strategy({"tenant_extraction": "host"})
        resolve_strategy({
            "tenant_extraction": "jwt",
            "jwt_secret": "...",
            "jwt_claim": "org_id",
        })
        resolve_strategy({"tenant_extraction": lambda req: req.get_header("...")})

    Args:
        config: Mapping carrying the ``tenant_extraction`` key plus
            strategy-specific options.

    Returns:
        Instance conforming to ``TenantExtractionStrategy``.

    Raises:
        ValueError: When ``tenant_extraction`` is missing, holds an
            unknown string value, or required strategy-specific keys
            (e.g., ``jwt_secret`` for the JWT strategy) are absent.
    """
    extraction = config.get("tenant_extraction")
    if extraction is None:
        msg = (
            "Config missing required 'tenant_extraction' key. "
            "Available options: 'header', 'host', 'jwt', or a callable."
        )
        raise ValueError(msg)

    if extraction == "header":
        return HeaderStrategy(header_name=str(config.get("header_name", "X-Tenant-Id")))

    if extraction == "host":
        return HostStrategy()

    if extraction == "jwt":
        try:
            jwt_secret = config["jwt_secret"]
        except KeyError as exc:
            msg = (
                "'jwt_secret' is required when tenant_extraction='jwt'. "
                "Configure a non-empty secret (use a 32+ byte random value "
                "for HS256)."
            )
            raise ValueError(msg) from exc
        return JWTStrategy(
            secret=str(jwt_secret),
            claim=str(config.get("jwt_claim", "tenant_id")),
            algorithm=str(config.get("jwt_algorithm", "HS256")),
        )

    if callable(extraction):
        return CallableStrategy(extraction)

    msg = (
        f"Unknown tenant_extraction value: {extraction!r}. "
        "Expected 'header', 'host', 'jwt', or a callable."
    )
    raise ValueError(msg)
