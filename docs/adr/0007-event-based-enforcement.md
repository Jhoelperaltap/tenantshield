# ADR-0007 -- Event-based enforcement for SQLAlchemy adapter

**Status:** Accepted.
**Date:** 2026-05-15.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.
**Related:** Decision 4 (Phase 3 kickoff ratificación), DR-021 (write
enforcement), DR-022 (read enforcement), ADR-0006 (SQLAlchemy 2.0+
only).

## Context

Phase 3 introduces TenantShield's SQLAlchemy adapter. SQLAlchemy 2.0+
provides a rich event system as the architectural extension point for
ORM behavior modification:

- **Mapper-scoped events** (per model class): ``before_insert``,
  ``before_update``, ``before_delete``. Fire at flush time
  per-instance.
- **Session-scoped events** (per ``Session`` class):
  ``do_orm_execute``. Fires per-statement, providing access to the
  statement before execution and allowing in-place modification.
- **Connection-scoped events**: lower-level, not used by this adapter.

Three architectural alternatives were considered for tenant
enforcement:

1. **Event listeners** (this ADR).
2. ``with_loader_criteria`` only for reads + ``Session`` subclass for
   writes.
3. Custom ``Session`` subclass plus ``Query`` interception (SA 1.x
   style).

## Decision

TenantShield's SQLAlchemy adapter uses event listeners exclusively
for tenant enforcement:

- **Write enforcement** (DR-021): mapper-scoped ``before_insert``,
  ``before_update``, ``before_delete`` events on tenant-aware models.
  Each event handler validates tenant context coherence; auto-injects
  on INSERT if unset; raises ``CrossTenantAccessError`` on mismatch.
- **Read enforcement** (DR-022): session-scoped ``do_orm_execute``
  event. For SELECT statements on tenant-aware models (discovered
  via ``__tenantshield_tenant_aware__`` sentinel attribute), injects
  ``with_loader_criteria()`` to filter by active tenant scope.

Mapper-scoped registration happens at decorator-application time via
``register_write_enforcement(cls)`` invoked by ``@tenant_aware``.
Session-scoped registration happens once at module import time.

### Loader-criteria pattern: static expression, not lambda

``with_loader_criteria`` accepts either a static SQL expression or a
Python callable (lambda). When a callable is used, SA caches the
compiled expression by lambda body alone, **ignoring closure
variables by default**. A lambda capturing the runtime tenant via
default argument (``lambda cls, t=tenant: cls.tenant_id == t``) is
reused with the wrong tenant on subsequent queries because the cache
key does not include ``t``.

The SA adapter uses a static expression
(``entity.tenant_id == tenant``) rebuilt per event invocation. This
binds the current tenant correctly and bypasses the lambda cache
issue. Verified empirically during Tarea 3A.5 implementation (Smoke 3
revealed wrong-tenant binding with lambda; Smoke 3b confirmed
correctness with static expression).

### Missing-scope semantics: fall-through (not raise)

Unlike Django adapter's ``TenantAwareManager`` which raises
``MissingTenantContextError`` when ``Model.objects`` is accessed
without an active scope, the SA adapter's ``do_orm_execute`` handler
falls through (returns unfiltered results) when no active scope.

Rationale: the SA adapter's enforcement is orthogonal to scope
binding. Adopters compose the adapter with a middleware (or manual
``tenant_scope()`` usage) to establish the scope. The middleware
layer (Sub-fase 3B, DR-016) provides the stricter
raise-on-missing-scope behavior with configurable strategies. The
adapter alone treats absence of scope as "no filter intent", not as
"deny by default".

This is a conscious divergence from Django adapter behavior. Django's
``_unscoped`` escape hatch covers the same need from the opposite
direction (opt-out of filtering). SA adapter's fall-through covers
it as the default.

Adopters wanting strict-on-missing-scope behavior should:

- Use the SA-session middleware from Sub-fase 3B (when materialized).
- Or wrap their session usage explicitly inside ``tenant_scope()``.

## Alternatives considered

### Alternative A -- ``with_loader_criteria`` only for reads + ``Session`` subclass for writes

Use ``with_loader_criteria`` directly without ``do_orm_execute``
wrapper; require adopters to apply it manually. Override ``Session``
class for writes.

**Rejected because:** requires adopter awareness and manual
application of ``with_loader_criteria`` on every query. Bypassable.
The ``Session`` subclass approach forces adopter inheritance from a
custom Session class, breaking framework-agnostic philosophy (kickoff
Decision 3-A).

### Alternative B -- Custom ``Session`` subclass + ``Query`` interception

Subclass ``Session``, override ``query()`` and ``execute()`` to
inject filtering logic.

**Rejected because:** SA 2.0 deprecates ``query()`` in favor of
``select()`` + ``execute()``. Custom Session forces inheritance,
breaks framework-agnostic design, and is incompatible with
``Session`` factories (``sessionmaker``, ``scoped_session``).

### Alternative C -- Manual query filtering per-query

Adopters explicitly call ``query.filter(Model.tenant_id == current_tenant())``
on each query.

**Rejected because:** no enforcement, entirely opt-in. Provides no
guarantee against bypass; defeats the library's purpose of automated
multi-tenant safety.

## Consequences

### Positive

- Adopters write standard SA 2.0 code; enforcement is transparent.
- Framework-agnostic: works with FastAPI, Flask, Starlette, raw
  scripts; ``Session`` abstraction sufficient.
- Single source of truth: ``@tenant_aware`` decorator marks models;
  events perform enforcement.
- Cross-adapter coherence: write pattern parallels Django adapter's
  ``pre_save``/``pre_delete`` signals; same exception types and
  field semantics.
- Performance: filter injected via SA's native
  ``with_loader_criteria``; the static expression is rebuilt
  per-query but the resulting compiled SQL is cached normally by
  SA's query plan cache.

### Negative

- **Bulk operations bypass mapper events.**
  ``session.execute(insert(Foo).values([...]))`` and similar bulk
  patterns bypass ``before_insert``/``before_update``/``before_delete``
  events. Documented as constraint in DR-024 (Tarea 3A.6).
- **Raw SQL bypasses all enforcement.**
  ``session.execute(text("SELECT ..."))`` is not an ORM statement.
  DR-023 documents this as an intentional semantic constraint
  (mirrors ``_base_manager`` in Django adapter).
- **Read fall-through without scope** is the default. Adopters who
  want strict-on-missing-scope rely on the middleware in Sub-fase 3B.
- **Import-time side effect.** ``event.listen(Session, "do_orm_execute", ...)``
  registers once per process when ``events.py`` is imported.
  Generally safe; could register duplicates if the module were
  re-imported via unusual paths (does not happen with Python's normal
  module cache).

### Cross-adapter pattern alignment

| Operation | Django adapter | SQLAlchemy adapter |
|---|---|---|
| Write INSERT | ``pre_save`` signal | ``before_insert`` event |
| Write UPDATE | ``pre_save`` signal | ``before_update`` event |
| Write DELETE | ``pre_delete`` signal | ``before_delete`` event |
| Read filter | Custom ``Manager`` queryset | ``do_orm_execute`` + ``with_loader_criteria`` |
| Missing context (write) | ``MissingTenantContextError`` | Same |
| Missing context (read) | ``MissingTenantContextError`` | Fall-through (see above) |
| Cross-tenant violation | ``CrossTenantAccessError`` | Same |
| Operation identifier | ``f"{op}.{sender.__qualname__}"`` | ``f"{event}.{mapper.class_.__qualname__}"`` |

Adopters migrating Django adapter code patterns to SA adapter
encounter a consistent mental model for writes. Exception types are
reused, error field semantics identical, enforcement layers
conceptually parallel.

## Empirical evidence

Sub-fase 3A Tareas 3A.3-3A.5 empirically validated:

- ``before_insert``, ``before_update``, ``before_delete`` fire at
  flush time per-instance (Tareas 3A.3, 3A.4 empirical scenarios).
- ``do_orm_execute`` fires per-statement and exposes
  ``column_descriptions`` for entity discovery (Tarea 3A.5 Smoke 1).
- ``with_loader_criteria`` injection via ``.options()`` works
  correctly for both single-entity and multi-entity statements
  (Tarea 3A.5 Smoke 2).
- **Lambda closure variables are NOT part of SA's loader-criteria
  cache key** (Tarea 3A.5 Smoke 3 returned wrong-tenant rows when
  using ``lambda cls, t=tenant: cls.tenant_id == t``). Static SQL
  expression bypasses the issue (Smoke 3b verified).
- Sentinel attribute discovery via
  ``__tenantshield_tenant_aware__`` reliably identifies decorated
  models at session event time.

## References

- SQLAlchemy 2.0 events documentation:
  <https://docs.sqlalchemy.org/en/20/orm/events.html>.
- SQLAlchemy ``with_loader_criteria`` documentation:
  <https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#sqlalchemy.orm.with_loader_criteria>.
- ADR-0006 (SQLAlchemy 2.0+ only).
- DR-021 (write enforcement via mapper-scoped events).
- DR-022 (read enforcement via session-scoped events).
- DR-023 (raw SQL bypass semantics, TBD per Tarea 3A.7).
- DR-024 (bulk operations bypass, TBD per Tarea 3A.6).
- PHASE_3A_KICKOFF.md sec 1 Decision 4-A (ratified by Owner).
- Django adapter ``signals.py`` for cross-adapter pattern reference.

---

**End of ADR-0007.**
