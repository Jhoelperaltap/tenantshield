"""DjangoRequestAdapter -- wraps HttpRequest to conform to RequestProtocol.

Per Decision iii-A from the Sub-fase 4B kickoff: framework-specific
adapter wrappers live at adapter level (Django adapter), NOT inside
``tenantshield.strategies``. This module bridges Django's HttpRequest
API (``META`` dict, ``get_host()`` method) to the framework-agnostic
``tenantshield.strategies.RequestProtocol`` surface (``get_header``
+ ``get_host``).

The adapter is instantiated by Django-side strategy subclasses
internally; adopters never see it directly. Their existing
``strategy.extract(http_request)`` calls continue working unchanged
(Decision 6-A backward-compatibility preservation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest


class DjangoRequestAdapter:
    """Wraps Django ``HttpRequest`` to conform to ``RequestProtocol``.

    Implements the two-method RequestProtocol surface
    (``get_header(name)`` + ``get_host()``) backed by Django's
    HttpRequest API:

    - ``get_header(name)`` -> looks up ``request.headers[name]``
      (Django 2.2+ case-insensitive header access).
    - ``get_host()`` -> calls ``request.get_host()`` (Django method
      that returns host string with optional port).

    Args:
        request: Django ``HttpRequest`` instance to wrap.
    """

    def __init__(self, request: HttpRequest) -> None:
        self._request = request

    def get_header(self, name: str) -> str | None:
        """Return header value (case-insensitive lookup), or ``None``."""
        # Django ``headers`` attribute (since 2.2) is a case-insensitive
        # mapping; ``.get(name)`` returns ``None`` when absent.
        return self._request.headers.get(name)

    def get_host(self) -> str:
        """Return the host string (may include port)."""
        return self._request.get_host()
