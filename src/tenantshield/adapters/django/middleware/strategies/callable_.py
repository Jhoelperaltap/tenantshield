"""CallableStrategy -- delegate tenant extraction to a user-supplied callable.

The module is named ``callable_`` (trailing underscore) to avoid shadowing
the Python builtin ``callable()``. Users import the class from the
package: ``from tenantshield.adapters.django.middleware.strategies
import CallableStrategy``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield import TenantId
from tenantshield.adapters.django.exceptions import TenantExtractionError

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest


class CallableStrategy:
    """Delegate tenant extraction to a user-supplied callable.

    Example:
        def my_extractor(request) -> str:
            return request.session.get("tenant_id", "")

        strategy = CallableStrategy(my_extractor)

    The callable must accept an HttpRequest and return a string (the
    tenant id). Empty / falsy returns (None, "", 0) are treated as
    "missing tenant" and raise TenantExtractionError.

    Implements the TenantExtractionStrategy Protocol structurally.
    """

    def __init__(self, fn: Callable[[HttpRequest], str]) -> None:
        """Initialize with the extractor callable.

        Args:
            fn: Callable that accepts an HttpRequest and returns the
                tenant id as a string.
        """
        self._fn = fn

    def extract(self, request: HttpRequest) -> TenantId:
        """Invoke the callable and return its result as TenantId.

        Raises:
            TenantExtractionError: when the callable returns an
                empty/falsy value.
        """
        result = self._fn(request)
        if not result:
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason="Callable strategy returned empty value",
                context={"result": repr(result)},
            )
        return TenantId(result)
