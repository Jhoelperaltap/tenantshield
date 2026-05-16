"""SQLAlchemy adapter ASGI/WSGI middleware.

Provides ASGI and WSGI middleware classes that bind tenant context
to per-request scope using ``lifecycle.SessionScope`` internally.

Tenant resolution: middleware accepts a ``resolve_tenant`` callable
parameter. Example::

    TenantSessionMiddleware(
        app,
        resolve_tenant=lambda request: request.headers.get("X-Tenant-ID"),
    )

NO Phase 2B strategy reuse: Phase 2B ``TenantExtractionStrategy``
classes are Django-bound (use ``request.META``, ``request.get_host()``).
Cross-adapter strategy unification deferred per BLOCKER #30
resolution (post-empirical analysis in Sub-fase 3B Tarea 3B.0).
See ADR-0008.

Stricter read-without-scope enforcement (raise on missing tenant)
is opt-in via middleware configuration; standalone SA adapter
retains fall-through semantics per DR-022.

See ADR-0008 (middleware lifecycle design pattern; materialized
evidence-based post-Tarea 3B.2).
"""

from __future__ import annotations

# Implementation in Tareas 3B.3 + 3B.4.
