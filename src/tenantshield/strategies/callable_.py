"""CallableStrategy -- delegate tenant extraction to a user-supplied callable.

Module named ``callable_`` (trailing underscore) to avoid shadowing the
Python builtin ``callable()``. Import: ``from tenantshield.strategies
import CallableStrategy``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield._types import TenantId

if TYPE_CHECKING:
    from collections.abc import Callable

    from tenantshield.strategies.base import RequestProtocol


class CallableStrategy:
    """Delegate tenant extraction to an adopter-supplied callable.

    Contract:

    - Callable receives a ``RequestProtocol``-conforming request and
      returns a string tenant identifier (or empty / ``None`` to
      signal no tenant).
    - Empty / falsy returns (``None``, ``""``, ``0``) are treated as
      "no tenant applicable" and the strategy returns ``None``
      (fall-through semantics).
    - Exceptions raised by the callable propagate as-is; adopters are
      responsible for surfacing them as ``TenantExtractionError`` if
      semantically appropriate.

    Example::

        def my_extractor(request) -> str:
            # adopter logic, e.g., session-cookie lookup
            return request.get_header("X-Session") or ""

        strategy = CallableStrategy(my_extractor)

    Implements ``TenantExtractionStrategy`` structurally.

    Args:
        fn: Callable that accepts a ``RequestProtocol``-conforming
            object and returns the tenant id as a string.
    """

    def __init__(self, fn: Callable[[RequestProtocol], str]) -> None:
        self._fn = fn

    def extract(self, request: RequestProtocol) -> TenantId | None:
        """Invoke the callable and return its result as ``TenantId`` or ``None``."""
        result = self._fn(request)
        if not result:
            return None
        return TenantId(result)
