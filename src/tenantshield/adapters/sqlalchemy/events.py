"""SQLAlchemy event listener registration for tenant enforcement.

Hosts event listener functions for:

- ``before_insert``: write enforcement (Tarea 3A.3).
- ``before_update`` / ``before_delete``: write enforcement (Tarea 3A.4).
- ``do_orm_execute``: read filtering (Tarea 3A.5).

Implementation materialized incrementally across Tareas 3A.3-5.
"""

from __future__ import annotations
