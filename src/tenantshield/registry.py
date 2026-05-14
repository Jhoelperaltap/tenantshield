"""Tenant-aware model registry.

This module defines :class:`RegistryEntry` (metadata about a tenant-aware
model) and :class:`ModelRegistry` (a thread-safe container of entries).
The :data:`default_registry` instance and the module-level convenience
functions are added in sub-task 1C.2.
"""

from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tenantshield.exceptions import ConfigurationError

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True, slots=True, kw_only=True)
class RegistryEntry:
    """Metadata about a tenant-aware model.

    Attributes:
        model: The model class.
        tenant_field: Name of the attribute/column that carries the tenant id.
    """

    model: type
    tenant_field: str


class ModelRegistry:
    """Registry of tenant-aware models.

    A registry maps model classes to their tenant metadata. Two registries
    are independent; users who need isolation construct their own instance.
    The package exposes a ``default_registry`` instance for the common case,
    and module-level convenience functions delegate to it (added in 1C.2).

    Thread-safety: register/unregister/iteration operations are protected
    by an internal ``RLock``. Read-only queries (``is_registered``, ``get``)
    are also locked for consistency; the performance impact is negligible at
    registry sizes typical of real applications (hundreds of models).
    """

    def __init__(self) -> None:
        self._entries: dict[type, RegistryEntry] = {}
        self._lock = threading.RLock()

    def register(self, model: type, *, tenant_field: str = "tenant_id") -> None:
        """Register ``model`` as tenant-aware.

        Idempotent: registering the same model twice with the same
        ``tenant_field`` is a no-op. Registering with a different
        ``tenant_field`` raises :class:`ConfigurationError`.

        Args:
            model: The model class to register.
            tenant_field: Name of the attribute/column carrying the tenant id.

        Raises:
            ConfigurationError: if ``model`` is already registered with a
                different ``tenant_field``.
        """
        with self._lock:
            existing = self._entries.get(model)
            if existing is not None:
                if existing.tenant_field != tenant_field:
                    msg = (
                        f"Model {model.__qualname__!r} already registered with "
                        f"tenant_field={existing.tenant_field!r}; "
                        f"cannot re-register with tenant_field={tenant_field!r}."
                    )
                    raise ConfigurationError(msg)
                return
            self._entries[model] = RegistryEntry(model=model, tenant_field=tenant_field)

    def unregister(self, model: type) -> None:
        """Unregister ``model``. If not registered, this is a no-op."""
        with self._lock, contextlib.suppress(KeyError):
            del self._entries[model]

    def is_registered(self, model: type) -> bool:
        """Return ``True`` if ``model`` is registered as tenant-aware."""
        with self._lock:
            return model in self._entries

    def get(self, model: type) -> RegistryEntry:
        """Return the :class:`RegistryEntry` for ``model``.

        Args:
            model: The model class to look up.

        Returns:
            The :class:`RegistryEntry` associated with ``model``.

        Raises:
            ConfigurationError: if ``model`` is not registered.
        """
        with self._lock:
            entry = self._entries.get(model)
            if entry is None:
                msg = f"Model {model.__qualname__!r} is not registered as tenant-aware."
                raise ConfigurationError(msg)
            return entry

    def clear(self) -> None:
        """Remove all registered models. Primarily for tests."""
        with self._lock:
            self._entries.clear()

    def __iter__(self) -> Iterator[RegistryEntry]:
        """Iterate over registered entries.

        Iteration takes a snapshot under lock; concurrent modifications
        during iteration do not affect the snapshot.
        """
        with self._lock:
            snapshot = list(self._entries.values())
        return iter(snapshot)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


__all__ = [
    "ModelRegistry",
    "RegistryEntry",
]
