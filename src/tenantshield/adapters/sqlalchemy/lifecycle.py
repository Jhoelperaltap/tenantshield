"""SQLAlchemy adapter session lifecycle management.

Provides framework-agnostic abstractions for binding tenant context
to SQLAlchemy ``Session`` lifecycle:

- ``SessionScope``: context manager binding tenant scope around
  session operations.
- ``bind_session_to_tenant()``: helper invoked at session
  initialization.

Used as the core abstraction underlying ``middleware.py`` ASGI/WSGI
wrappers. Adopters can use ``SessionScope`` directly in any context
(CLI, background workers, custom integration).

Tenant resolution accepts callable resolvers, NOT Phase 2B strategy
classes (which are Django-bound). Cross-adapter strategy unification
deferred per BLOCKER #30 resolution; see ADR-0008.

See ADR-0008 (middleware lifecycle design pattern; materialized
evidence-based post-Tarea 3B.2).
"""

from __future__ import annotations

# Implementation in Tareas 3B.1 + 3B.2.
