"""AsgiRequestAdapter -- wraps ASGI scope dict to conform to RequestProtocol.

Per Decision iii-A from the Sub-fase 4B kickoff: framework-specific
adapter wrappers live at adapter level (SA adapter), NOT inside
``tenantshield.strategies``. This module bridges the ASGI ``scope``
dict structure to the framework-agnostic
``tenantshield.strategies.RequestProtocol`` surface
(``get_header(name)`` + ``get_host()``).

The adapter exposes ASGI headers list-of-byte-tuples as a
case-insensitive string lookup, and derives the host string from the
``host`` header (the canonical ASGI source).

Adopter usage::

    from tenantshield.adapters.sqlalchemy import (
        AsgiRequestAdapter,
        HeaderStrategy,
        TenantSessionMiddleware,
    )

    strategy = HeaderStrategy()

    def resolve_tenant(scope):
        return strategy.extract(AsgiRequestAdapter(scope))

    app = TenantSessionMiddleware(asgi_app, resolve_tenant=resolve_tenant)

This composition realizes the cross-adapter strategy unification:
the same ``HeaderStrategy`` instance can be used by Django adapter
(wrapping ``HttpRequest`` via ``DjangoRequestAdapter``) and SA adapter
(wrapping ASGI ``scope`` via ``AsgiRequestAdapter``). See
``TenantSessionMiddleware`` resolver dual-mode (Sub-fase 4A.5) for
sync vs async resolver patterns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class AsgiRequestAdapter:
    """Wraps an ASGI ``scope`` dict to conform to ``RequestProtocol``.

    ASGI scope structure (per the ASGI spec):

    - ``scope["headers"]``: ``list[tuple[bytes, bytes]]`` with header
      names lowercased per the spec.
    - ``scope.get("server")`` / ``scope.get("client")``: optional
      ``(host, port)`` tuples (not directly used here).

    The adapter implements ``get_header(name)`` via case-insensitive
    lookup over the headers list (decoding latin-1 per RFC 7230), and
    ``get_host()`` via the ``host`` header (which ASGI servers
    populate from the HTTP ``Host`` header).

    Args:
        scope: ASGI scope mapping. Adopters typically obtain this from
            an ASGI middleware ``__call__(scope, receive, send)``
            invocation.
    """

    def __init__(self, scope: Mapping[str, Any]) -> None:
        self._scope = scope

    def get_header(self, name: str) -> str | None:
        """Return header value (case-insensitive lookup), or ``None``.

        ASGI header names are lowercased bytes; comparison normalizes
        the lookup name to lowercase bytes for direct match.
        """
        target = name.lower().encode("latin-1")
        headers: list[tuple[bytes, bytes]] = list(self._scope.get("headers", []))
        for h_name, h_value in headers:
            if h_name.lower() == target:
                return h_value.decode("latin-1")
        return None

    def get_host(self) -> str:
        """Return host string from the ``Host`` header.

        Returns an empty string when the ``Host`` header is absent;
        strategies treating empty host as fall-through (e.g.,
        ``HostStrategy``) will return ``None``.
        """
        return self.get_header("host") or ""
