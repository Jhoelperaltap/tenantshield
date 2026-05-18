"""CallableStrategy -- Django adapter shim over ``tenantshield.strategies.CallableStrategy``.

Phase 4B Decision 6-A: refactor in-place, preserve Phase 2B contract.
The Django ``CallableStrategy`` preserves the Phase 2B contract that
adopter callables receive the **raw Django** ``HttpRequest`` (so they
can call ``request.GET.get(...)``, ``request.session[...]``, etc.).
This differs from the cross-adapter core ``CallableStrategy``, whose
callables receive a ``RequestProtocol``-conforming object.

The class subclasses core for ``isinstance`` conformance with the
``TenantExtractionStrategy`` Protocol but provides its own ``extract``
that bypasses ``DjangoRequestAdapter`` wrapping (Phase 2B adopter
callables expect raw HttpRequest, not the protocol surface).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenantshield._types import TenantId
from tenantshield.adapters.django.exceptions import TenantExtractionError
from tenantshield.strategies import CallableStrategy as _CoreCallableStrategy

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest


class CallableStrategy(_CoreCallableStrategy):
    """Delegate tenant extraction to a user-supplied callable (Phase 2B contract).

    Subclass of :class:`tenantshield.strategies.CallableStrategy` that
    preserves Phase 2B Django contract:

    1. Callable receives **raw** ``HttpRequest`` (not
       ``DjangoRequestAdapter``). Adopter callables can use the full
       Django API (``request.GET``, ``request.session``, etc.).
    2. Empty / falsy callable return raises ``TenantExtractionError``
       (the core returns ``None`` for the same condition).

    Example::

        def my_extractor(request) -> str:
            return request.session.get("tenant_id", "")

        strategy = CallableStrategy(my_extractor)

    Implements the TenantExtractionStrategy Protocol structurally
    (inherits structural conformance from
    ``tenantshield.strategies.CallableStrategy``).
    """

    def __init__(self, fn: Callable[[HttpRequest], str]) -> None:
        """Initialize with the extractor callable.

        Args:
            fn: Callable that accepts a Django ``HttpRequest`` and
                returns the tenant id as a string.
        """
        # Store via core ``__init__`` so ``self._fn`` is set with the
        # adopter's callable; we do not call ``super().extract`` because
        # the core class would wrap the request in adapter form, which
        # Phase 2B adopter callables do not expect.
        super().__init__(fn)  # type: ignore[arg-type]

    def extract(self, request: HttpRequest) -> TenantId:  # type: ignore[override]
        """Invoke the callable with the raw HttpRequest and return as TenantId.

        Type narrowing vs core is intentional per Phase 2B contract
        preservation (callable receives raw HttpRequest, not adapter).

        Raises:
            TenantExtractionError: when the callable returns an
                empty/falsy value (Phase 2B contract preservation).
        """
        result = self._fn(request)  # type: ignore[arg-type]
        if not result:
            raise TenantExtractionError(
                strategy_name=type(self).__name__,
                reason="Callable strategy returned empty value",
                context={"result": repr(result)},
            )
        return TenantId(result)
