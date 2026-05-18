# ADR-0010 -- Cross-adapter strategy unification for Phase 4B

**Status:** Accepted.
**Date:** 2026-05-17.
**Deciders:** Jhoelperaltap (Owner), Tech Lead (this codebase).
**Supersedes:** None.
**Superseded by:** None.
**Related:** Decision 4-A (top-level `tenantshield.strategies` module),
Decision 5-B (3 strategies + HostStrategy analog), Decision 6-A
(in-place Django refactor + re-export shim), Sub-fase 4B sub-decisions
(i) module structure per-file, (ii-B) `TenantExtractionError` retention
in `tenantshield.strategies`, (iii-A) adapter wrappers at adapter
level, DR-033 through DR-036 (Sub-fase 4B decisions), ADR-0007
(event-based enforcement; foundational architecture), ADR-0008 (Phase
3B middleware lifecycle; Phase 3B Django-bound strategy assumption
superseded here per BLOCKER #30 resolution), BLOCKER #30 (Phase 2B
Django-bound strategies; deferral closed empirically in Tarea 4B.5).

## Context

Sub-phase 2B introduced the four extraction strategies (`HeaderStrategy`,
`JWTStrategy`, `SubdomainStrategy`, `CallableStrategy`) inside the
Django adapter. These were Django-specific by construction: typed
against `django.http.HttpRequest`, accessing `request.META` / `.get_host()`
directly, and registered under
`tenantshield.adapters.django.middleware.strategies`.

Sub-fase 3B's SQLAlchemy middleware took a different approach by
explicit decision: a callable-resolver pattern (the adopter supplies a
function that maps an ASGI/WSGI request-like object to a tenant id).
BLOCKER #30 (raised in Sub-fase 3B Tarea 3B.0 empirical exploration)
documented the architectural choice: Phase 2B strategy classes could
not be reused from the SA adapter without significant refactoring,
because the Django coupling was per-call (`.META` lookups, `get_host`
method) rather than just a type annotation. Three resolution paths
were considered; **Path (c)** was ratified: defer strategy
unification, ship Sub-fase 3B with the callable-only resolver, and
revisit in a dedicated sub-fase.

Phase 4 ratified that dedicated sub-fase as **Sub-fase 4B**. The
problem this ADR addresses is the architecture for cross-adapter
strategy unification: where strategies live, how they bridge to
framework-specific request types, and how Phase 2B Django adopters
preserve their import paths and contract.

## Decision

Phase 4B introduces a new top-level core module,
`tenantshield.strategies`, hosting framework-agnostic strategies that
operate on a minimal `RequestProtocol` abstraction. Adapter-specific
request wrappers (`DjangoRequestAdapter` in the Django adapter,
`AsgiRequestAdapter` in the SQLAlchemy adapter) bridge framework
request types to the protocol; the strategies themselves are unaware
of either framework.

### Architectural pillars

1. **`RequestProtocol` minimal surface (Decision 4-A; DR-033).** A
   two-method `typing.Protocol`: `get_header(name) -> str | None` and
   `get_host() -> str`. Tarea 4B.0 empirical inspection confirmed these
   two methods cover all four built-in strategies' requirements. The
   protocol is `@runtime_checkable` for ergonomic isinstance checks in
   tests and adapter wrapper conformance verification.

2. **Adapter wrappers at adapter level (Decision iii-A).** Framework
   bridging code lives where the framework is known. The Django adapter
   owns `DjangoRequestAdapter` (wrapping `HttpRequest`); the SA adapter
   owns `AsgiRequestAdapter` (wrapping the ASGI scope dict). Core
   strategies have no framework imports.

3. **`HostStrategy` generic replaces Django-specific `SubdomainStrategy`
   (Decision 5-B; DR-036).** The Phase 2B subdomain extraction logic
   (split on `:` for port, then on `.` for labels, leftmost label as
   tenant) is HTTP-standard and not Django-specific; generalizing
   through `RequestProtocol.get_host()` produces a strategy reusable
   across adapters. Phase 2B Django adopters keep the
   `SubdomainStrategy` name via subclass alias (Decision 6-A).

4. **In-place Django refactor with re-export shim (Decision 6-A;
   DR-034).** The four Phase 2B Django strategies become thin
   subclasses of the core strategies. Each subclass overrides
   `extract(request: HttpRequest) -> TenantId` to: (a) wrap the
   `HttpRequest` in a `DjangoRequestAdapter`, (b) call
   `super().extract(adapter)`, (c) translate the core's two-tier
   contract (return `None` for missing) back to the Phase 2B
   single-tier contract (raise `TenantExtractionError`). Adopter
   imports (`from tenantshield.adapters.django.middleware.strategies
   import HeaderStrategy`) and Phase 2B raise-on-missing behavior are
   preserved exactly; Tarea 4B.2 verified 117/117 existing Django
   strategy tests pass unchanged.

5. **Adopter-facing callable surfaces preserve framework-native types.**
   The Django `CallableStrategy` subclass deliberately does NOT pass
   the `DjangoRequestAdapter` to adopter callables; it passes the raw
   `HttpRequest`. Phase 2B adopters wrote callables expecting the full
   Django API (`request.GET`, `request.session`, etc.), and those
   callables would break if substituted with a protocol-only wrapper.
   Architectural principle (captured as Pool 4B datapoint #5):
   *protocol abstractions are internal to the strategy class; adopter-
   facing surfaces speak the adopter's native idiom*. The cross-adapter
   core `CallableStrategy`, in contrast, passes the `RequestProtocol`-
   conforming object to the callable, because cross-adapter adopters
   write callables against the protocol.

6. **Cross-adapter `resolve_strategy()` factory (Decision 4-A).** A
   single factory function in `tenantshield.strategies` produces
   strategies usable via both adapters. Misconfiguration raises
   `ValueError` (Python-idiomatic). The Django adapter's pre-existing
   `resolve_strategy` is retained separately with
   `ImproperlyConfigured` semantics per the Phase 2B / DPRJ-2 contract;
   Tarea 4B.4 verified the Django factory continues to raise the
   Django-idiomatic error for missing `jwt_secret`. Two factories
   coexist; a future post-1.0 consolidation may merge them with an
   adapter-specific error-translation shim.

7. **`TenantExtractionError` in `tenantshield.strategies`
   (Decision ii-B).** The core `TenantExtractionError` lives with the
   classes that raise it. The Django adapter keeps its own
   `tenantshield.adapters.django.exceptions.TenantExtractionError`
   (distinct class) with the Phase 2B positional constructor; the
   Django strategy subclasses translate core errors to the Django-
   namespaced class via `from exc` chaining per Rule 62.

### Empirical validation

Tarea 4B.5 demonstrated end-to-end:

- A single `HeaderStrategy()` / `HostStrategy()` / `JWTStrategy(...)` /
  `CallableStrategy(...)` instance extracts identical tenant values
  via both `DjangoRequestAdapter(django_request)` and
  `AsgiRequestAdapter(asgi_scope)`. Same Python object, identical
  output across adapter boundaries (8 integration tests).
- `resolve_strategy()` output strategies work via both adapters
  (3 integration tests covering header / host / JWT factory cases).
- Error parity: `JWTStrategy` raising `TenantExtractionError` for
  invalid signature behaves identically across adapter paths (1
  parity test).

## Alternatives considered

### Alternative A -- New async-specific strategy hierarchy

Define `AsyncTenantExtractionStrategy` protocol with
`async def extract(...)`. Adapters implement async variants paralelo to
the synchronous strategies.

**Rejected because:**

- Header/host/JWT/callable extraction is fundamentally synchronous
  work (string parsing, dict lookup, signature verification on bytes
  in-process); no benefit from async signatures.
- Async resolver requirement for tenant lookup against external
  systems is already handled by `TenantSessionMiddleware`'s dual-mode
  resolver (Tarea 4A.5); adopters needing async tenant resolution from
  a database compose an async callable into `resolve_tenant`, not into
  the strategy class itself.
- Duplicating the strategy hierarchy doubles the maintenance surface.

### Alternative B -- Adapter-only strategies (no cross-adapter core)

Keep each adapter's strategies fully framework-specific. Cross-adapter
adopters write per-framework strategy code or use callable resolvers.

**Rejected because:**

- BLOCKER #30 deferral was explicitly raised to be closed in a
  dedicated sub-fase; deferring indefinitely accumulates architectural
  debt.
- Multi-framework adopters (the canonical use case for TenantShield) lose
  cross-adapter strategy coherence; same conceptual extraction (header,
  host, JWT) requires N implementations for N adapters.
- Future adapters (Tortoise, Peewee, etc.) would inherit a fragmented
  strategy infrastructure.

### Alternative C -- Strategies on raw framework request, runtime dispatch

Strategies accept `Any` request, use isinstance / hasattr to dispatch
to framework-specific extraction code per call.

**Rejected because:**

- Runtime branching inside every strategy invocation; performance and
  readability cost.
- Strategy code becomes a switchboard of `isinstance(req, HttpRequest)`
  / `isinstance(req, dict)` checks; defeats the abstraction's purpose.
- Adding a new adapter requires modifying every strategy class.

## Consequences

### Positive

- **BLOCKER #30 deferral closed.** Empirically verified end-to-end by
  Tarea 4B.5.
- **Phase 2B Django adopters: zero migration cost.** All Phase 2B
  imports + contract preserved through subclass shim (117/117 existing
  Django strategy tests pass unchanged, Tarea 4B.2).
- **Phase 3B SA adopters: additive gain.** The callable-resolver
  pattern continues to work unchanged; strategy classes are now
  available as an alternative composing through `AsgiRequestAdapter`.
- **Future adapters inherit unified strategies.** A future Tortoise /
  Peewee adapter only needs its own `*RequestAdapter` wrapper to reuse
  the four core strategies + `resolve_strategy()` factory.
- **Cross-adapter contract clarity.** Protocols, error classes, and
  factory function semantics are documented in a single place
  (`tenantshield.strategies`).

### Negative

- **Adapter wrapper overhead per request.** `DjangoRequestAdapter` and
  `AsgiRequestAdapter` are instantiated once per request before
  strategy invocation. Cost is one Python object allocation;
  empirically negligible but documented.
- **Type-system divergence between mypy and pyright on `callable()`
  narrowing.** The `resolve_strategy()` dispatch path
  `if callable(extraction): return CallableStrategy(extraction)` is
  fully type-safe under mypy but requires an explicit
  `cast("Callable[[RequestProtocol], str]", extraction)` under pyright
  strict mode (Pool 4B datapoint #6).
- **Two `resolve_strategy()` implementations coexist.** Core
  (`ValueError`) and Django adapter (`ImproperlyConfigured`) factories
  serve different error idioms. A future consolidation may merge them
  with an adapter-side error-translation shim; preserving Phase 2B
  contract took precedence in Sub-fase 4B.
- **Two `TenantExtractionError` classes coexist.** Core (kwarg-only
  constructor, `strategy_name: reason` message format) and Django
  adapter (positional constructor, reason-only message). Phase 2B
  adopter tests catch the Django-namespaced class; cross-adapter
  consumers catch the core class. Django strategy subclasses translate
  via `from exc` chaining per Rule 62.

## Cross-adapter pattern alignment

| Aspect | Django adapter | SQLAlchemy adapter |
|---|---|---|
| Adapter request wrapper | `DjangoRequestAdapter(HttpRequest)` | `AsgiRequestAdapter(ASGI scope dict)` |
| Strategy import (Phase 2B/3B legacy) | `tenantshield.adapters.django.middleware.strategies.*` | (Phase 3B used callable resolver only) |
| Strategy import (Phase 4B canonical) | Re-exports legacy path via subclass shim | Re-exports from `tenantshield.strategies` |
| `extract()` contract | raises `TenantExtractionError` on missing (Phase 2B) | returns `None` on missing (core contract) |
| Callable adopter param | raw `HttpRequest` (Phase 2B preserved) | `RequestProtocol`-conforming wrapper |
| `resolve_strategy` error class | `ImproperlyConfigured` (Django idiom, DPRJ-2 preserved) | n/a -- adopters use core `resolve_strategy` (`ValueError`) |
| `SubdomainStrategy` alias | yes (subclass of `HostStrategy`) | no (use `HostStrategy` directly) |

## Empirical evidence

Sub-fase 4B Tareas 4B.0-4B.5 empirically validated:

- 4-strategy Django coupling depth audit (Tarea 4B.0) -- minimal refactor
  scope per strategy (1-line API swaps + signature widening).
- `RequestProtocol` natural conformance: Django `HttpRequest` does NOT
  have `get_header(name)` method; adapter wrapper required (Tarea 4B.0).
- `tenantshield.strategies` module foundation (Tarea 4B.1): 27 unit
  tests covering 4 strategies + protocols + top-level re-exports.
- Django strategies subclass shim + `DjangoRequestAdapter` (Tarea
  4B.2): 117/117 existing Django strategy tests pass unchanged + 6
  new adapter conformance tests.
- SA adapter `AsgiRequestAdapter` + cross-adapter strategy re-exports
  (Tarea 4B.3): 12 unit tests covering wrapper + strategy integration.
- Cross-adapter `resolve_strategy()` factory (Tarea 4B.4): 9 unit
  tests covering dispatch + 3-path symbol identity (core / SA adapter /
  top-level `tenantshield`).
- Cross-adapter integration empirical proof (Tarea 4B.5): 8
  integration tests demonstrating same strategy instance + same
  factory output extracting identical results via both adapter
  wrappers.

## References

- Decisions (i), (ii-B), (iii-A) ratified in Tarea 4B.0 follow-up.
- Decision 4-A, 5-B, 6-A from the Phase 4 kickoff Mass A ratification.
- DR-033 (`RequestProtocol` minimal surface).
- DR-034 (in-place Django strategy refactor preserves public API).
- DR-035 (SA strategy class parity scope: re-exports only).
- DR-036 (`HostStrategy` generic host parser replaces
  `SubdomainStrategy`).
- ADR-0007 (event-based enforcement) -- foundational architecture
  enabling cross-adapter strategies as orthogonal layer.
- ADR-0008 (Phase 3B middleware lifecycle) -- Phase 3B callable-only
  resolver context; this ADR closes BLOCKER #30 deferral per Path (c)
  resolution promise.
- BLOCKER #30 (Phase 2B Django-bound strategies) -- deferral closed
  empirically in Tarea 4B.5.
- Tarea 4B.0 empirical findings (Django strategy coupling depth audit;
  `RequestProtocol` cross-adapter feasibility).
- Rule 60 (ADR forward-reference cleanup) -- applied via the ADR-0008
  reference update accompanying this ADR.
- Rule 62 (exception chaining via `raise X from exc`) -- applied in
  Django `JWTStrategy` subclass translating core errors to Django-
  namespaced errors.

---

**End of ADR-0010.**
