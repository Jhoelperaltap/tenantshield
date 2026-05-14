# TenantShield — Plan Maestro de Desarrollo

> **Documento de gobierno técnico del proyecto.**
> Autoridad: Tech Lead (sesión de chat).
> Ejecutor: Claude Code Console.
> Estado: v1.3 — Consolidación post-Sub-fase 1B.
> Última revisión: 2026-05-14.
> Tag de proyecto al revisar: `v0.0.3-alpha.0` (Sub-fase 1B cerrada).

Este documento define **qué se construye, cómo se construye, con qué calidad y en qué orden**. Cualquier desviación requiere justificación técnica documentada en el `CHANGELOG.md` bajo la sección `Decision Records`. No se acepta "lo hice así porque era más rápido". El código que no cumple los estándares de este documento **no entra a `main`**.

**Revisiones de este documento** se listan al final, en §10.

---

## 1. Visión del Producto

**TenantShield** es un motor de *enforcement* multi-tenant para Python. Su propósito es **eliminar por construcción** la posibilidad de filtraciones cross-tenant en aplicaciones SaaS, no mitigar sus síntomas.

### 1.1 Principios no negociables

1. **Deny-by-default.** Si no hay contexto de tenant explícito, cualquier query sobre un modelo tenant-aware **falla ruidosamente**. Silencio = bug latente.
2. **Zero-trust sobre el desarrollador.** Asumimos que un junior cansado un viernes a las 18:00 va a escribir `.all()` sin filtrar. El sistema lo debe detener.
3. **No magia oculta.** Toda intercepción es explícita, configurable, y auditable. Si el comportamiento depende de monkey-patching, debe documentarse de forma agresiva.
4. **Tipado estricto end-to-end.** `mypy --strict` + `pyright strict`. No hay `Any` sin comentario `# noqa: justified-any: <razón>`.
5. **Observabilidad por defecto.** Cada bloqueo, cada inyección de filtro, cada propagación de contexto emite eventos auditables.
6. **Compatibilidad declarada y probada.** Si decimos que soportamos Django 4.2 LTS, hay una matriz de CI que lo prueba en cada PR. Sin excepciones.
7. **Sin dependencias innecesarias.** Cada dependencia se justifica por escrito en el PR que la introduce.

### 1.2 Anti-objetivos (lo que TenantShield NO es)

- No es un *router* de bases de datos (no compite con `django-tenants` para schema-per-tenant).
- No es un sistema de RBAC ni de permisos a nivel de fila genérico.
- No es un ORM ni un wrapper de ORM. Es una **capa de enforcement** sobre ORMs existentes.

---

## 2. Stack Tecnológico (Decisiones Firmes)

| Área | Decisión | Justificación |
|---|---|---|
| Python mínimo | **3.11** | `Self`, `tomllib`, mejoras en `asyncio.TaskGroup`, contextvars maduros. |
| Python máximo CI | **3.13** | Última estable soportada. |
| Gestor de paquetes | **`uv`** | Velocidad, lockfile reproducible, gestión de toolchain. |
| Build backend | **`hatchling`** | PEP 517/621 limpio, sin Setuptools legacy. |
| Linter + formatter | **`ruff` + `ruff format`** | Sustituye flake8/isort/black; rapidísimo. |
| Type checking | **`mypy --strict`** (gate) + **`pyright`** (segunda opinión en CI) | Doble red de seguridad. |
| Tests | **`pytest`**, **`pytest-asyncio`**, **`pytest-cov`**, **`hypothesis`** | Estándar de facto + property-based. |
| Cobertura mínima | **95% líneas, 90% ramas** | No es decorativo: el CI falla por debajo. |
| Seguridad estática | **`bandit`**, **`pip-audit`**, **`semgrep`** (semgrep llega en Fase 5) | Tres ángulos diferentes. |
| Logging estructurado | **`structlog`** (dep base, DR-010) | Sustento de `AuditSink` built-in. Confirmado zero-dep transitiva al instalar. |
| Docs | **`mkdocs-material`** + **`mkdocstrings`** | Generación desde docstrings tipados. Se monta en sub-fase 1C. |
| Versionado | **SemVer 2.0.0** | Sin atajos. |
| Mensajes de commit | **Conventional Commits** | Habilita changelog automático. |
| CI | **GitHub Actions**, matriz `{3.11, 3.12, 3.13} × {django 4.2, 5.x} × {sqlalchemy 2.x}` (matriz multi-eje desde Fase 2) | |
| Licencia | **Apache-2.0** | Permisiva con cláusula de patentes; apta para enterprise. |
| Distribución | **PyPI** vía Trusted Publishing (OIDC, sin tokens) | |

Cualquier propuesta de cambio sobre esta tabla se debate en un *Architecture Decision Record* (`docs/adr/NNNN-titulo.md`) antes de implementarse. La infraestructura `docs/adr/` se materializa en sub-fase 1C.

---

## 3. Estructura del Repositorio

```
tenantshield/
├── pyproject.toml
├── uv.lock
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── .gitignore
├── .gitattributes
├── .editorconfig
├── .python-version
├── .pre-commit-config.yaml
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── security.yml
│   │   ├── bench.yml            (sub-fase 1C, ver §5 Sub-fase 1C)
│   │   ├── release.yml          (Fase 8)
│   │   └── docs.yml             (sub-fase 1C)
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
├── docs/                         (sub-fase 1C)
│   ├── index.md
│   ├── getting-started.md
│   ├── concepts/
│   ├── adapters/
│   ├── adr/
│   └── api/
├── src/
│   └── tenantshield/
│       ├── __init__.py
│       ├── py.typed
│       ├── _version.py
│       ├── _types.py              # ✅ sub-fase 1A
│       ├── context.py             # ✅ sub-fase 1A, refinado sub-fase 1B
│       ├── exceptions.py          # ✅ sub-fase 1A
│       ├── audit.py               # ✅ sub-fase 1B
│       ├── policies.py            # ✅ sub-fase 1B
│       ├── registry.py            # sub-fase 1C
│       ├── config.py              # Fase 2+
│       ├── adapters/              # Fase 2+
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── django/
│       │   ├── sqlalchemy/
│       │   ├── celery/
│       │   └── drf/
│       ├── asyncio/               # Fase 4
│       │   ├── __init__.py
│       │   └── propagation.py
│       └── testing/               # Fase 6
│           ├── __init__.py
│           ├── fixtures.py
│           ├── factories.py
│           └── generator.py
└── tests/
    ├── conftest.py               # fixtures globales (silent_audit, capture_audit; ampliable en 1C)
    ├── unit/
    ├── integration/              # Fase 2+
    │   ├── django/
    │   ├── sqlalchemy/
    │   └── celery/
    └── e2e/                      # Fase 6
```

**Regla:** `src/`-layout obligatorio. No se permite importar desde el directorio raíz durante el desarrollo; los tests siempre corren contra el paquete instalado en modo editable.

---

## 4. Arquitectura Core

### 4.1 Modelo conceptual

```
                ┌──────────────────────────────────────┐
                │           TenantContext              │
                │  (ContextVar — async-safe, isolated) │
                │  Emits CONTEXT_BOUND/RELEASED events │
                └──────────────────────────────────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  │                               │
        ┌─────────▼────────┐            ┌─────────▼─────────┐
        │  Policy Engine   │            │   Audit Bus       │
        │  - DenyByDefault │            │  - StructLogSink  │
        │  - AllowList     │            │  - InMemorySink   │
        │  - Chain         │            │  - NullSink       │
        │  - Decision:     │            │  - SINK_FAILURE   │
        │    Allow|Deny|   │            │    handling       │
        │    RequireScope  │            │                   │
        └─────────┬────────┘            └───────────────────┘
                  │
   ┌──────────────┼──────────────┬─────────────────┐
   │              │              │                 │
┌──▼───┐    ┌─────▼─────┐   ┌────▼────┐      ┌─────▼─────┐
│Django│    │SQLAlchemy │   │ Celery  │      │   DRF     │
│Adapt.│    │ Adapter   │   │ Adapter │      │  Adapter  │
└──────┘    └───────────┘   └─────────┘      └───────────┘
                  ▲
                  │ (Phase 2+, consumes ModelRegistry from sub-phase 1C)
```

### 4.2 Decisiones arquitectónicas clave

- **Contexto basado en `contextvars.ContextVar`.** Funciona en sync y async sin parches. Prohibido usar `threading.local()`.
- **Adapter Pattern estricto** con `typing.Protocol`. Cada adapter implementa el mismo contrato. Si un método no aplica, se lanza `NotImplementedError` explícito.
- **Extras opcionales** en `pyproject.toml`:
  - `tenantshield[django]`
  - `tenantshield[sqlalchemy]`
  - `tenantshield[celery]`
  - `tenantshield[drf]`
  - `tenantshield[all]`
  - `tenantshield[dev]` (para contributors)
- **`structlog` es dependencia base** (no extra). Razones documentadas en DR-010. `StructLogSink` siempre disponible al instalar `tenantshield`. Confirmado en Sub-fase 1B: structlog 25.5.0 instala sin deps transitivas adicionales.
- **Sin import-time side effects.** Importar `tenantshield` no monkey-patchea nada. El usuario activa los adapters explícitamente. El registry global de sinks de auditoría **empieza vacío** — el usuario hace `register_sink(...)` cuando quiera observabilidad.
- **Event bus síncrono y predecible.** No usamos un sistema pub/sub asíncrono por defecto; los eventos se emiten en línea y los sinks son responsables de no bloquear. Sinks que lanzan excepciones no rompen el bus (un evento `SINK_FAILURE` se emite a los otros sinks; el sink que falló se excluye para evitar recursión).
- **Decision sealed-por-convención.** `Decision = Allow | Deny | RequireScope` con `match` exhaustivo y `assert_never(d)` en el caso final. mypy/pyright detectan exhaustividad. La forma `|` (PEP 604) es el patrón canónico del proyecto para union types con target Python 3.10+.

### 4.3 `TenantId`: representación interna fijada

**Decisión arquitectónica (DR-009):** el identificador de tenant se representa internamente como un `typing.NewType` sobre `str`.

```python
from typing import NewType

TenantId = NewType("TenantId", str)
```

**Reglas vinculantes:**

1. **El bus interno es siempre `str`.** Cualquier valor que cruce las fronteras del sistema (logs estructurados, headers Celery, serialización de eventos de auditoría, contextvars, persistencia) viaja como string. Esto elimina ambigüedad de serialización y garantiza que un tenant identificado en Django como `int` y en Celery como `UUID` no se vean como tenants distintos.
2. **El usuario es responsable de la coerción en la frontera de entrada.** Si su columna `tenant_id` en Django es `IntegerField`, su middleware convierte a `str(request.user.tenant_id)` antes de llamar a `bind_tenant(...)`. TenantShield no intenta inferir el tipo nativo.
3. **El tipado público usa `TenantId`, no `str` plano.** Las firmas de funciones (`current_tenant() -> TenantContext`, `bind_tenant(tenant_id: TenantId, ...)`) usan `TenantId` para que el lector entienda la semántica sin recurrir a la documentación.
4. **Conversión explícita en el código del usuario.** El usuario hace `TenantId(str(value))` para construir un `TenantId` válido. No hay magia: `NewType` es solo una marca para mypy/pyright, en runtime es un `str` puro.
5. **Igualdad por valor.** Dos `TenantId` con el mismo string son iguales. No hay normalización (case-folding, trimming, etc.) automática en la frontera de TenantShield. Si el usuario quiere normalización, la aplica antes de construir el `TenantId`.

### 4.4 Jerarquía de excepciones (implementada en Sub-fase 1A)

```
TenantShieldError                       # Base
├── ConfigurationError                  # Setup incorrecto del paquete
├── TenantContextError                  # Problemas con el contexto
│   ├── MissingTenantContextError       # No hay tenant en contexto cuando se requiere
│   └── AmbiguousTenantContextError     # Conflicto entre contextos anidados
├── EnforcementError                    # Base para violaciones
│   ├── CrossTenantAccessError          # Acceso a datos de otro tenant
│   ├── UnscopedQueryError              # Query sin scope tenant
│   └── CrossTenantJoinError            # Join entre tenants distintos
└── AdapterError                        # Problemas en un adapter específico
```

Cada excepción transporta campos estructurados (frozen dataclass o slots) y expone `to_dict()` para serialización al bus de auditoría. Implementación completa: `src/tenantshield/exceptions.py`.

### 4.5 Modelo de decisiones de Policy (implementado en Sub-fase 1B)

`Policy` evalúa una `Operation` y retorna una `Decision`. Las tres formas de decisión:

```
Decision = Allow | Deny | RequireScope

Allow                  # incondicional
Deny(reason: str)      # operación rechazada
RequireScope(          # operación condicional a aplicación de filtro
    filter_spec: Mapping[str, object]
)
```

**DR-011: `filter_spec` typing.** `RequireScope.filter_spec` es `Mapping[str, object]` libre. Los adapters de Fase 2+ pueden refinar con TypedDicts propios que sean asignación-compatibles con `Mapping[str, object]`. No imponemos schema en Sub-fase 1B porque no hay consumidor todavía.

**Composición:** `ChainPolicy(policies=(p1, p2, ...))` aplica políticas en orden. Primer `Deny` o `RequireScope` gana (short-circuit). Si todas retornan `Allow`, retorna `Allow`.

**Helper `evaluate_and_audit(policy, operation)`:** evalúa + emite `POLICY_ALLOW` o `POLICY_DENY` al bus de auditoría según la decisión. `RequireScope` se trata como `POLICY_ALLOW` con el scope en el payload (es informacional, no denial).

---

## 5. Fases de Desarrollo

Cada fase tiene **objetivo, entregables, criterios de aceptación y Definition of Done (DoD)**. **No se pasa a la siguiente fase sin DoD verde.**

### Fase 0 — Cimientos del Repositorio ✅ COMPLETADA

Cerrada el 2026-05-13 con tag `v0.0.1-alpha.0` en commit `b6262c6`. Documento de cierre: `PHASE_0_CLOSURE.md`. Detalles en `CHANGELOG.md`.

---

### Fase 1 — Núcleo (descompuesta en tres sub-fases)

**Justificación de la descomposición (DR-008):** Fase 1 original era demasiado grande para tratarse como unidad operativa. Se descompone en tres sub-fases con entregables verificables independientes, cada una con su propio kickoff, sus propios criterios de aceptación, y su propio cierre.

---

#### Sub-fase 1A — Identidad y excepciones ✅ COMPLETADA

Cerrada el 2026-05-14 con tag `v0.0.2-alpha.0` en commit `909d32d`. Documento de cierre: `PHASE_1A_CLOSURE.md`. Detalles en `CHANGELOG.md`.

**Resumen de entregas:**

- `tenantshield._types`: `TenantId` (NewType sobre str).
- `tenantshield.exceptions`: 10 clases de excepción con campos estructurados y `to_dict()`.
- `tenantshield.context`: `TenantContext`, `tenant_scope` (sync), `atenant_scope` (async), `current_tenant`, `try_current_tenant`, `bind_tenant`.
- `tenantshield.__init__`: superficie pública de 18 nombres.
- 55 tests + 1 smoke benchmark con techo catastrófico.
- 100% cobertura líneas/ramas en módulos productivos.

---

#### Sub-fase 1B — Políticas y auditoría ✅ COMPLETADA

Cerrada el 2026-05-14 con tag `v0.0.3-alpha.0` en commit `02667b8`. Documento de cierre: `PHASE_1B_CLOSURE.md`. Detalles en `CHANGELOG.md`.

**Resumen de entregas:**

- `tenantshield.audit`: `AuditEvent`, `AuditEventType` (StrEnum), `AuditSink` Protocol, sinks built-in (`NullSink`, `InMemorySink`, `StructLogSink`), registry thread-safe con `register_sink`/`unregister_sink`/`emit`, lógica `SINK_FAILURE` tolerante a fallos sin recursión infinita.
- `tenantshield.policies`: `Operation`, `OperationType`, `Decision` (sealed-by-convention con `Allow | Deny | RequireScope`), `Policy` Protocol, tres policies built-in (`DenyByDefaultPolicy`, `AllowListPolicy`, `ChainPolicy`), helper `evaluate_and_audit`.
- Modificación de `tenantshield.context`: `tenant_scope` y `atenant_scope` emiten `CONTEXT_BOUND`/`CONTEXT_RELEASED` al entrar/salir.
- `tenantshield.__init__`: superficie pública expandida a 38 nombres; `emit` re-exportado como `audit_emit`.
- Fixtures `silent_audit` y `capture_audit` en `tests/conftest.py` global.
- 114 tests (de los 55 previos) + 2 smoke benchmarks con techo catastrófico.
- 100% cobertura líneas/ramas en los 6 módulos productivos.
- DR-010 (`structlog` como dep base) y DR-011 (`filter_spec` como `Mapping[str, object]` libre) registrados en CHANGELOG.

---

#### Sub-fase 1C — Registro, documentación y cierre de Fase 1

**Objetivo:** cerrar el núcleo de Fase 1 con el registro de modelos tenant-aware y montar la infraestructura mínima de documentación para que el proyecto pueda escalar.

**Entregables:**

- `tenantshield.registry`:
  - `ModelRegistry`: registro tipado de modelos tenant-aware.
  - `register_model(model: type, tenant_field: str = "tenant_id")` decorador y función.
  - `is_tenant_aware(model: type) -> bool`.
  - `get_tenant_field(model: type) -> str`.
  - Descubrimiento opcional vía marker class `TenantAware` o decorador.
  - **Aislamiento por aplicación**: dos proyectos que importen TenantShield no comparten registro. La decisión arquitectónica exacta (module-level dict, singleton class, ContextVar de registry) se fija en el kickoff de 1C tras dry-run.
- Infraestructura `docs/`:
  - `docs/index.md`, `docs/getting-started.md`, `docs/concepts/` (overview de los conceptos de Fase 1: identity, exceptions, context, policies, audit, registry), `docs/adapters/` (placeholder con README explicando que llega en Fase 2+), `docs/api/` (autogenerada con mkdocstrings).
  - `docs/adr/0001-commit-signing-deferral.md` — materializa DR-003 como ADR formal.
  - `mkdocs.yml` con tema Material y plugin `mkdocstrings`.
  - **Alcance acotado para 1C** (decisión tentativa, confirmación en kickoff): scaffold + ADR-0001 + getting-started mínima + API reference autogenerada. Documentación expandida (guías profundas, ejemplos detallados, comparativas con otras librerías) se difiere a Fase 8 (hardening).
- Workflows:
  - `.github/workflows/docs.yml`: build de docs en cada PR, deploy a GitHub Pages en push a `main`.
  - `.github/workflows/bench.yml`: job dedicado de benchmarks corriendo en CI Linux con los markers `slow` activados. Verifica los budgets estrictos del roadmap (`tenant_scope` < 1µs mediana, `emit()` < 10µs mediana sobre 10.000 iteraciones). **Materialización en 1C** (deferido desde 1A y 1B).
- Actualización del `pyproject.toml`:
  - `mkdocs-material` y `mkdocstrings[python]` añadidos al extra `dev`.
- Bump de versión: `_version.py` → `__version__ = "0.1.0a0"`. Primer commit que toca esto sincroniza con el tag final de Fase 1.

**Criterios de aceptación:**

- 100% cobertura de líneas en `registry.py`, ≥ 95% ramas.
- `mkdocs build --strict` pasa sin warnings.
- Documentación generada incluye API reference completa de `context`, `exceptions`, `policies`, `audit`, `registry`.
- ADR-0001 escrito y revisado.
- Job `bench.yml` corre en CI Linux y los benchmarks pasan sus budgets estrictos (no solo el techo catastrófico local).
- Los 47 tests pre-1C (de 1A) + 67 nuevos de 1B + tests de 1C siguen verdes.

**DoD:** Tag `v0.1.0-alpha` aplicado. **Cierra Fase 1 completa.** Documento de cierre de Fase 1 consolidado (no solo de Sub-fase 1C).

---

### Fase 2 — Adapter Django + DRF

**Objetivo:** Enforcement total sobre Django ORM y DRF.

**Entregables:**

- `tenantshield.adapters.django.apps.TenantShieldConfig`: instalable como app de Django.
- `TenantAwareManager` / `TenantAwareQuerySet`:
  - Filtra automáticamente por el campo de tenant.
  - `.all()`, `.filter()`, `.get()`, `.update()`, `.delete()` bloqueados si no hay contexto.
  - `.unscoped()` explícito (con log de auditoría, exige permiso configurable).
- Detector de joins cross-tenant: analiza `select_related`/`prefetch_related` y rechaza relaciones entre modelos tenant-aware con campos `tenant_id` distintos.
- Middleware `TenantContextMiddleware`: extrae tenant del request (estrategia configurable: subdomain, header, JWT claim, callable).
- Integración DRF:
  - `TenantScopedViewSetMixin`.
  - Permission class `IsSameTenant`.
  - Serializers que rechazan FK cross-tenant en validación.
- Señales `pre_save`/`pre_delete` que validan que `instance.tenant_id == current_tenant().tenant_id`.

**Criterios de aceptación:**

- Test integration suite contra Django 4.2 LTS y 5.x.
- Tests de regresión que reproducen los 5 patrones clásicos de leak (lista en `docs/concepts/known-leaks.md`).
- Bench: overhead de filtrado < 5% sobre query baseline.
- `mypy --strict` pasa con `django-stubs` configurado.
- DRF browsable API funcional en `examples/01_django/`.

**DoD:** Tag `v0.2.0-alpha`. Aplicación demo desplegada en `examples/01_django/` con README de uso.

---

### Fase 3 — Adapter SQLAlchemy

**Objetivo:** Misma rigurosidad sobre SQLAlchemy 2.x.

**Entregables:**

- `TenantAwareMixin` para declarative models.
- Event listeners en `Session`:
  - `do_orm_execute`: inyecta filtro `WHERE tenant_id = :ctx_tenant`.
  - `before_flush`: valida que instancias nuevas/modificadas pertenezcan al tenant actual.
- `ScopedSession` helper que liga sesión a contexto.
- Detección estática de joins peligrosos vía análisis de `select()` expressions.
- Soporte tanto sync como async (`AsyncSession`).

**Criterios de aceptación:**

- Tests contra SQLite y PostgreSQL (testcontainers).
- Async tests con `pytest-asyncio` strict mode.
- Bench equivalente al de Django.
- Cero `# type: ignore` en el adapter sin justificación.

**DoD:** Tag `v0.3.0-alpha`. Ejemplo en `examples/02_sqlalchemy/`.

---

### Fase 4 — Async + Celery

**Objetivo:** Propagación de contexto a través de fronteras de proceso/thread.

**Entregables:**

- `tenantshield.asyncio.propagation`: utilidades para `TaskGroup`, `gather`, executores.
- `tenantshield.adapters.celery`:
  - Signals `before_task_publish` (serializa tenant en headers) y `task_prerun` (deserializa y entra al scope).
  - Rechazo de tareas sin tenant header cuando el modo strict está activo.
  - Soporte para Celery 5.x.
- Documentación clara sobre interacción con `eager mode` y testing.

**Criterios de aceptación:**

- Tests con un broker real (Redis vía testcontainers).
- Test de "chain of tasks" verificando propagación 5 niveles.
- Test que demuestra que un worker sin contexto **rechaza** la tarea.

**DoD:** Tag `v0.4.0-alpha`. Ejemplo en `examples/03_celery/`.

---

### Fase 5 — Query Analyzer

**Objetivo:** Detección proactiva, no solo reactiva.

**Entregables:**

- Analizador runtime que registra cada query ejecutada, su modelo, su filtro tenant resultante, y emite `AuditEvent` clasificado.
- Modo `paranoid`: cualquier query a modelo tenant-aware que termine en SQL sin cláusula `WHERE tenant_id = ?` lanza excepción **incluso si el adapter ya filtró** (validación de segundo nivel inspeccionando el SQL final).
- Analizador estático (CLI): `tenantshield analyze <path>` que escanea código por antipatrones:
  - `.objects.all()` directo en modelos tenant-aware.
  - Uso de `unscoped()` sin docstring justificativo.
  - FKs entre modelos tenant-aware sin restricción declarada.
- Reportes en JSON, SARIF (para GitHub Code Scanning) y texto.
- Integración con `semgrep` (se añade al stack en esta fase).

**Criterios de aceptación:**

- El analizador estático corre sobre el propio repositorio en CI y reporta 0 issues.
- Tests con corpus de "código malo conocido" — debe detectar el 100%.

**DoD:** Tag `v0.5.0-alpha`.

> **Nota:** según §6 #10 enmendado, **antes** del tag `v0.5.0-alpha`, el owner configura su llave de signing local y se empieza a firmar commits. Los commits previos no se reescriben.

---

### Fase 6 — Auto Test Generator

**Objetivo:** Generar suites de tests de aislamiento a partir de los modelos del usuario.

**Entregables:**

- `tenantshield gen-tests --framework {django,sqlalchemy} --output <dir>`:
  - Descubre modelos tenant-aware.
  - Genera pytest suites que crean 2 tenants, datos en cada uno, y verifican que:
    - `.all()` desde tenant A no ve datos de B.
    - APIs HTTP devuelven 404 al pedir recursos de otro tenant.
    - Operaciones de escritura cross-tenant son rechazadas.
  - Genera fixtures reusables.
- Documentación de cómo extender los generadores.

**Criterios de aceptación:**

- Sobre las apps demo, generar tests y que pasen.
- Mutación: si se elimina un guardarraíl del producto, al menos un test generado falla.

**DoD:** Tag `v0.6.0-beta`.

---

### Fase 7 — Integración CI / Plugin

**Objetivo:** Que adoptar TenantShield sea trivial en CI.

**Entregables:**

- GitHub Action publicada: `tenantshield/analyze-action@v1`.
- Plugin de `pre-commit` publicado.
- Plantillas de configuración (`tenantshield.toml`) para casos comunes.

**Criterios de aceptación:**

- Acción ejecutándose en un repo demo público.
- Documentación con ejemplos copiables.

**DoD:** Tag `v0.7.0-beta`.

---

### Fase 8 — Hardening + Release 1.0

**Objetivo:** Pulido, fuzzing, auditoría externa, documentación final.

**Entregables:**

- Fuzzing con `hypothesis` sobre el motor de políticas (≥ 1M ejemplos sin fallo).
- Revisión de seguridad documentada (`SECURITY_AUDIT.md`).
- Benchmarks publicados (`docs/benchmarks/`).
- Documentación completa, incluida guía de migración desde `django-tenants` / scoped manual.
- Página de tutorial.

**Criterios de aceptación:**

- Cobertura ≥ 97%.
- 0 issues `bandit` HIGH/MEDIUM.
- 0 vulnerabilidades `pip-audit`.
- `pyright strict` con 0 errores.
- Documentación revisada palabra por palabra.

**DoD:** Tag `v1.0.0`. Publicación en PyPI vía OIDC.

---

## 6. Reglas Inquebrantables de Calidad

Estas reglas aplican **a todo PR, desde el commit cero**.

1. **Un PR = una unidad lógica.** PRs > 400 líneas se rechazan salvo refactor explícito.
2. **Todo PR incluye tests.** Bug fix sin test de regresión = rechazo automático.
3. **Cobertura no baja.** El gate de CI bloquea PRs que reduzcan cobertura.
4. **Sin `print`, sin `TODO` sin issue asociado.** `# TODO: ...` debe llevar `(#123)`.
5. **Docstrings obligatorios** en toda función pública (estilo Google).
6. **Type hints completos** en toda función. `Any` se justifica.
7. **Errores tipados.** No se lanza `Exception` ni `RuntimeError` genéricos.
8. **Logs estructurados** vía `structlog`. Nada de `logger.info(f"...")` con interpolación.
9. **Sin `# type: ignore` sin código de error específico y comentario.** Aplicable también a `# noqa: <RULE>` — si la regla efectivamente no dispara, RUF100 detectará el noqa innecesario.
10. **Commits firmados (SSH/GPG/sigstore) a partir de v0.5.0-alpha**, una vez el owner configure su llave de signing local. Los commits previos no se reescriben para firmarse retroactivamente. ADR-0001 (materializado en sub-fase 1C) documenta formalmente esta decisión.
11. **Reviewer ≠ Autor.** En este proyecto: yo (tech lead chat) reviso lo que ejecuta Claude Code.
12. **CHANGELOG actualizado en cada PR** bajo `[Unreleased]`.
13. **Atribución exclusiva al owner.** Ningún artefacto del proyecto (commit, PR, issue, documentación, metadatos del paquete) acredita herramientas de IA. La regla aplica a Claude, Copilot, Cursor, Aider, o cualquier otra asistencia automatizada presente o futura. La política pública se codifica en `CONTRIBUTING.md` §Attribution.
14. **Falsos positivos de linters: se excluyen archivos, no se silencian reglas.** Si una regla legítima dispara sobre contenido no-código (documentación legacy en otro idioma, datos de prueba, ejemplos), el archivo se excluye explícitamente en la config de la herramienta. Silenciar la regla globalmente está prohibido salvo justificación documentada en un ADR.
15. **Reportes de BLOCKER por CVE.** Cuando un BLOCKER es por CVE, el reporte inicial debe incluir, como mínimo: ID de la CVE, severidad cualitativa o CVSS, vector de ataque, `fix_versions`, y aplicabilidad al contexto de uso del proyecto. Sin esos cinco campos, el Tech Lead no puede decidir sin pedir información adicional y la iteración se duplica.
16. **Bumps en cadena por mitigación de CVE.** Cuando la remediación de una CVE implica forced upgrades transitivos, cada bump debe pasar por *changelog review cualitativo* antes de aplicarse, no solo verificación de resolución de dependencias.
17. **Verificación per-file con `--no-cov`.** El primer comando de verificación per-tarea (`pytest <file> -v`) incluye `--no-cov` cuando el gate global `--cov-fail-under=95` está activo. La verificación de cobertura es responsabilidad exclusiva del comando final per-módulo (`pytest --cov=<module> --cov-report=term-missing`).
18. **Context managers usan `Generator`/`AsyncGenerator`, no `Iterator`/`AsyncIterator`.** El typeshed actual marca `Iterator[T]` como tipo de retorno de `@contextmanager` como deprecated. Las firmas canónicas son `Generator[T, None, None]` y `AsyncGenerator[T, None]`.
19. **Conventional Commits exige veracidad descriptiva.** Cuando una tarea se aparta del kickoff por enmienda autorizada, el commit message refleja la realidad post-enmienda, no el contenido literal del kickoff.
20. **Criterios de Hypothesis: `failing` no `invalid`.** La métrica de validación de propiedades es `0 failing examples`, no `0 invalid examples`. `invalid` es métrica de eficiencia de generación, no de calidad.
21. **El kickoff manda sobre el GO message.** Cuando un mensaje de GO del Tech Lead generaliza un criterio que el kickoff trata de forma específica, el kickoff manda.
22. **Specs literales pasan filtro de imports usados.** Cuando el Tech Lead dicta contenido literal de un archivo, debe verificar que cada import declarado se usa al menos una vez en el cuerpo. F401 detecta imports muertos; emitirlos en una spec es fallo del Tech Lead.
23. **Tests de propiedades inestables usan techo catastrófico, no budget estricto.** Cuando una métrica varía significativamente entre runs en el mismo hardware por jitter del sistema, el test enforce un techo catastrófico (eg. 50x el peor caso observado) y deja los budgets estrictos para CI ephemeral aislado.
24. **`try/except/pass` → `contextlib.suppress(<ExcType>)` siempre.** Ruff SIM105 dispara cuando `try/except/pass` cubre una sola excepción específica. `contextlib.suppress` es el patrón canónico moderno: comunica intención explícitamente y elimina simultáneamente SIM105 y S110 (que dispara sobre `pass`).
25. **`Union[X, Y, Z]` → `X | Y | Z` por defecto (PEP 604).** En proyectos con target Python 3.10+ y toolchain moderno, la forma `|` es funcionalmente equivalente a `typing.Union` para todos los usos relevantes y permite además `isinstance(x, MyAlias)` directo.
26. **Consolidaciones que afectan dependencias se materializan en `pyproject.toml` en el mismo commit.** Si una consolidación de fase registra un DR que menciona una dep nueva, el commit que registra el DR también añade la dep al manifest. Evita el gap roadmap/manifest documentado en E10.
27. **Specs literales del Tech Lead usan ASCII puro.** Docstrings y mensajes que el ejecutor copia textualmente a archivos son ASCII puro. Caracteres Unicode "tipográficos" (`×`, `—`, `…`, etc.) disparan RUF002/RUF003.
28. **`# pragma: no cover` legítimo en Protocol stubs y `assert_never` branches.** Dos casos: cuerpos `...` de métodos en `Protocol` clases (contrato, no implementación) y `case _: assert_never(d)` al final de un `match` exhaustivo (defensivo, debe ser inalcanzable en valid typing).
29. **`@dataclass(frozen=True, slots=True)` sobre clases sin campos: quitar `slots=True`.** Bug conocido en CPython (lineage de `bpo-44806`, presente en 3.13.13 verificado empíricamente). El `__setattr__` generado falla con `TypeError` en lugar de `FrozenInstanceError`. Para clases marker sin campos, `frozen=True` se mantiene, `slots=True` se omite. Cuando los campos existen, `slots=True` se conserva.
30. **Imports en tests/fixtures van top-level salvo ciclo estructural verificado empíricamente.** PLC0415 dispara sobre imports inline ornamentales. Tests no participan en grafos de import circular del paquete porque no son importados por nada. La regla "imports al top de archivo" aplica sin excepción en tests.

---

## 7. Flujo de Trabajo entre Tech Lead y Claude Code

Para cada fase o sub-fase:

1. **Tech Lead** (chat) realiza *spec validation by dry-run* del kickoff antes de emitirlo. El dry-run cubre: (a) viabilidad del código que se escribe; (b) viabilidad de cómo lo verifica el toolchain con su config real, ejecutando mentalmente cada comando contra los plugins activos; (c) filtro de imports usados (regla §6 #22); (d) verificación empírica de ciclos cuando se prescribe deferred imports (con `python -c "import X"` antes de fijar la spec); (e) verificación de qué reglas de ruff disparan sobre cada patrón con la config actual.
2. **Tech Lead** emite la instrucción de inicio referenciando este documento.
3. **Claude Code** propone un *plan de implementación detallado* (lista de archivos, firmas de funciones clave, riesgos identificados).
4. **Tech Lead** aprueba, corrige o rechaza el plan.
5. **Claude Code** implementa **una tarea a la vez**, no la fase completa de golpe.
6. Tras cada tarea: ejecutar `pre-commit`, `pytest`, `mypy`, `ruff`. Reportar resultado completo según el formato §3 del kickoff vigente.
7. **Tech Lead** valida contra criterios de aceptación.
8. Solo cuando todos los criterios están verdes, se cierra la fase con su tag y su documento de cierre.

**Reglas para Claude Code:**

- No avanzar a la siguiente tarea sin confirmación si surge ambigüedad.
- No introducir dependencias no listadas en la tabla de stack sin pedir aprobación.
- No silenciar errores de lint/type. Si surge, escalarlo.
- No "limpiar" código no relacionado con la tarea en curso.
- Si algo de este documento parece estar mal, **señalarlo antes de actuar**, no improvisar.
- Cuando una instrucción del Tech Lead contiene un error técnico verificable (delimitador equivocado, ref de git inexistente, etc.) y la *intent* es clara, la adaptación está autorizada y se documenta en el reporte. Si la intent es ambigua, sigue siendo BLOCKER.
- Cuando se invoca `ruff check --fix` o cualquier herramienta de autocorrección, **verificar el resultado** vía `git diff` antes de pasar al siguiente comando.

**Tipología de BLOCKERs:**

- **BLOCKER trivial:** un fallo con una sola resolución idiomática evidente alineada con precedente del propio proyecto. Reporte de 3-5 líneas: qué disparó, qué precedente lo resuelve, autorización pedida. La disciplina de **parar y reportar** es absoluta; lo que cambia es la dimensión analítica del reporte.
- **BLOCKER analítico:** disyuntiva entre opciones con trade-offs reales. Reporte con tabla de opciones (pros/contras) y recomendación argumentada.

El criterio para distinguir: ¿existe al menos una segunda opción razonable que no sea trivialmente peor? Si no, es trivial.

**Decisiones arquitectónicas y coherencia top-level:**

- Cuando un símbolo aparece en `tenantshield.__all__` (API pública top-level), su módulo de origen debe importarlo a runtime, no en `TYPE_CHECKING`. La decisión `TYPE_CHECKING` per-módulo debe verificarse contra el plan global de re-exportación antes de aprobar la spec.

**Tests modelan al usuario:**

- Los tests importan desde `tenantshield` top-level cuando el símbolo esté re-exportado. Sub-fases en construcción pueden importar de submódulos directamente hasta que la tarea de re-exportación lo añada a `__init__.py`. Acceso a símbolos privados (`_SINKS_REGISTRY`, etc.) es legítimo dentro de tests del propio paquete.

---

## 8. Definition of Done global (release 1.0)

- [ ] Soporte probado: Django 4.2 + 5.x, SQLAlchemy 2.x, Celery 5.x, DRF 3.14+.
- [ ] Python 3.11, 3.12, 3.13.
- [ ] Cobertura ≥ 97% líneas, ≥ 92% ramas.
- [ ] `mypy --strict` y `pyright` con cero errores.
- [ ] Cero issues de seguridad MEDIUM+ abiertos.
- [ ] Documentación completa publicada.
- [ ] Al menos 3 ejemplos runnable en `examples/`.
- [ ] Benchmarks publicados con metodología reproducible.
- [ ] Changelog completo.
- [ ] Paquete publicado en PyPI con firmas Sigstore.

---

## 9. Próximo paso inmediato

Sub-fase 1B cerrada. **Sub-fase 1C en preparación.**

El siguiente paso operativo es la emisión del `PHASE_1C_KICKOFF.md` por parte del Tech Lead, con dry-run aplicado. El dry-run debe resolver:

- Diseño detallado de `ModelRegistry` y `TenantAware` marker class.
- Decisión arquitectónica sobre **aislamiento del registry por aplicación** (module-level dict, singleton, ContextVar de registry — opciones con trade-offs reales, decisión documentada como DR-012 si corresponde).
- Integración inicial de `mkdocs-material` + `mkdocstrings[python]` y estructura mínima de `docs/`.
- ADR-0001 (commit signing deferred to v0.5.0-alpha) como archivo formal en `docs/adr/`.
- Bump de `_version.py` a `0.1.0a0`.
- Workflow `bench.yml` con job dedicado de benchmarks en CI Linux verificando los budgets estrictos.
- Posibles refactors operacionales: marker `property` para tests property-based (deuda D1 del closure 1B), `_clear_registry` fixture global (deuda D2 del closure 1B).

Cuando el owner confirme disponibilidad para arrancar 1C, el Tech Lead emite el kickoff y Claude Code propone el plan de implementación detallado antes de la primera tarea atómica.

---

## 10. Historial de revisiones

| Versión | Fecha | Tag al momento | Cambios |
|---|---|---|---|
| 1.0 | 2026-05-13 (inicio Fase 0) | — | Versión inicial. |
| 1.1 | 2026-05-13 (cierre Fase 0) | `v0.0.1-alpha.0` | Consolidación post-Fase 0: §6 #13/#14/#15/#16 nuevos, §6 #10 enmendado, §4.3 TenantId NewType (DR-009), §5 Fase 1 descompuesta (DR-008), §7 *spec validation by dry-run*. |
| 1.2 | 2026-05-14 (cierre Sub-fase 1A) | `v0.0.2-alpha.0` | Consolidación post-Sub-fase 1A: §2 `structlog` añadido a stack (DR-010), §3 `bench.yml` previsto, §4.1 sinks built-in actualizados, §4.2 `structlog` como dep base documentada, §4.4 jerarquía marcada como implementada, §5 Sub-fase 1A marcada como ✅ con tag y resumen, §5 Sub-fase 1B refinada (Decision sealed type, benchmark techo catastrófico), §5 Sub-fase 1C con bump de versión explícito, §6 nuevas reglas #17-#23, §7 BLOCKER trivial vs analítico + verificación de autofixes + coherencia top-level. |
| 1.3 | 2026-05-14 (cierre Sub-fase 1B) | `v0.0.3-alpha.0` | Consolidación post-Sub-fase 1B: §2 `structlog` zero-dep confirmado, §3 `bench.yml` movido a sub-fase 1C, `conftest.py` global notado, §4.1 diagrama actualizado con audit bus completo + SINK_FAILURE handling, §4.2 decisión sealed-por-convención formalizada, §4.5 NUEVO modelo de decisiones de Policy con DR-011, §5 Sub-fase 1B marcada como ✅ con tag y resumen, §5 Sub-fase 1C refinada (alcance acotado de docs, bench.yml dentro de scope, decisión arquitectónica de aislamiento del registry pendiente), §6 nuevas reglas #24-#30 (contextlib.suppress, X\|Y over Union, deps en manifest, ASCII puro en specs, pragma:no cover en Protocols/assert_never, frozen+slots+empty workaround, imports top-level en tests), §6 #9 reforzado con noqa policy, §7 dry-run expandido con verificación empírica de ciclos y filtros de ruff, §7 tests modelan al usuario nuevo. |

---

*Fin del documento.*
