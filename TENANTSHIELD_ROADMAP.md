# TenantShield — Plan Maestro de Desarrollo

> **Documento de gobierno técnico del proyecto.**
> Autoridad: Tech Lead (sesión de chat).
> Ejecutor: Claude Code Console.
> Estado: v1.6 — Consolidación post-Sub-fase 2B.
> Última revisión: 2026-05-15.
> Tag de proyecto al revisar: `v0.2.0-alpha.1` (Sub-fase 2B cerrada).

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
| Logging estructurado | **`structlog`** (dep base, DR-010) | Sustento de `StructLogSink` built-in. Confirmado zero-dep transitiva. |
| Docs | **`mkdocs-material`** + **`mkdocstrings[python]`** (dep `dev`, instalada en Sub-fase 1C) | Generación desde docstrings tipados. |
| Versionado | **SemVer 2.0.0** | Sin atajos. Version y tag desync deliberado durante una fase, convergen al cierre. |
| Mensajes de commit | **Conventional Commits** | Habilita changelog automático. |
| CI | **GitHub Actions**, matriz `{3.11, 3.12, 3.13} × {django 4.2, 5.x} × {sqlalchemy 2.x}` (matriz multi-eje desde Fase 2) | |
| Licencia | **Apache-2.0** | Permisiva con cláusula de patentes; apta para enterprise. |
| Distribución | **PyPI** vía Trusted Publishing (OIDC, sin tokens) | |

Cualquier propuesta de cambio sobre esta tabla se debate en un *Architecture Decision Record* (`docs/adr/NNNN-titulo.md`) antes de implementarse. La infraestructura `docs/adr/` se materializó en Sub-fase 1C (ADR-0001).

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
│   │   ├── ci.yml                # ✅ Fase 0
│   │   ├── security.yml          # ✅ Fase 0
│   │   ├── docs.yml              # ✅ Sub-fase 1C
│   │   ├── bench.yml             # ✅ Sub-fase 1C
│   │   └── release.yml           # Fase 8
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
├── docs/                          # ✅ Sub-fase 1C
│   ├── index.md
│   ├── getting-started.md
│   ├── concepts/
│   ├── adapters/                  # placeholder hoy, contenido en Fase 2+
│   ├── api/
│   └── adr/
│       └── 0001-commit-signing-deferral.md
├── src/
│   └── tenantshield/
│       ├── __init__.py            # ✅ Fase 1, 44 nombres en __all__
│       ├── py.typed
│       ├── _version.py            # ✅ Fase 1, __version__ = "0.1.0a0"
│       ├── _types.py              # ✅ Sub-fase 1A
│       ├── context.py             # ✅ Sub-fase 1A, refinado Sub-fase 1B
│       ├── exceptions.py          # ✅ Sub-fase 1A
│       ├── audit.py               # ✅ Sub-fase 1B
│       ├── policies.py            # ✅ Sub-fase 1B
│       ├── registry.py            # ✅ Sub-fase 1C
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
    ├── conftest.py                # fixtures globales (silent_audit, capture_audit)
    ├── unit/                      # ✅ Fase 1
    ├── integration/               # Fase 2+
    │   ├── django/
    │   ├── sqlalchemy/
    │   └── celery/
    └── e2e/                       # Fase 6
```

**Regla:** `src/`-layout obligatorio. No se permite importar desde el directorio raíz durante el desarrollo; los tests siempre corren contra el paquete instalado en modo editable.

---

## 4. Arquitectura Core (Implementada en Fase 1)

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
                  │ (Phase 2+, consumes ModelRegistry from Sub-phase 1C)
                  │
            ┌─────┴──────────┐
            │ ModelRegistry  │
            │ - class + def. │
            │   instance     │
            │ - decorator    │
            │ - thread-safe  │
            └────────────────┘
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
- **`structlog` es dependencia base** (no extra). Razones documentadas en DR-010. `StructLogSink` siempre disponible al instalar `tenantshield`.
- **Sin import-time side effects.** Importar `tenantshield` no monkey-patchea nada. El usuario activa los adapters explícitamente. El registro de sinks de auditoría **empieza vacío** — el usuario hace `register_sink(...)` cuando quiera observabilidad. El `default_registry` de modelos también **empieza vacío** — el usuario registra modelos explícitamente.
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

**DR-011: `filter_spec` typing.** `RequireScope.filter_spec` es `Mapping[str, object]` libre. Los adapters de Fase 2+ pueden refinar con TypedDicts propios que sean asignación-compatibles con `Mapping[str, object]`. No imponemos schema porque no había consumidor en Sub-fase 1B y sigue sin haberlo al cierre de Fase 1.

**Composición:** `ChainPolicy(policies=(p1, p2, ...))` aplica políticas en orden. Primer `Deny` o `RequireScope` gana (short-circuit). Si todas retornan `Allow`, retorna `Allow`.

**Helper `evaluate_and_audit(policy, operation)`:** evalúa + emite `POLICY_ALLOW` o `POLICY_DENY` al bus de auditoría según la decisión. `RequireScope` se trata como `POLICY_ALLOW` con el scope en el payload (es informacional, no denial).

### 4.6 ModelRegistry (implementado en Sub-fase 1C)

**Decisión arquitectónica (DR-012):** el registro de modelos tenant-aware se expone como una **clase `ModelRegistry`** con una **instancia global `default_registry`**, más funciones módulo-level de conveniencia (`register_model`, `is_tenant_aware`, `get_tenant_field`) que delegan a la instancia default.

**Reglas vinculantes:**

1. **Uso casual:** el usuario decora modelos con `@register_model` (sin paréntesis), `@register_model(tenant_field="x")` (con argumentos), o llama `register_model(Cls)` directamente. Todas las formas registran en `default_registry`.
2. **Uso con aislamiento:** el usuario que necesita aislar registros (tests con scope local, microservicios embebidos en monorepo) construye su propia `ModelRegistry()` y la usa explícitamente. No comparte estado con `default_registry`.
3. **Adapters de Fase 2+:** aceptan parámetro opcional `registry: ModelRegistry | None = None`. Si `None`, usan `default_registry`. Sin breaking change para el usuario casual.
4. **Detección semántica:** `is_tenant_aware(cls)` consulta el registry. **No** se usa `isinstance` ni `issubclass` (no hay marker class por herencia). Esto evita acoplar al patrón de herencia múltiple, que es delicado con Django `Meta` abstract y SQLAlchemy `DeclarativeBase`.
5. **Thread-safety:** todas las operaciones del registry (incluso queries de solo lectura) van bajo un `threading.RLock`. La iteración toma snapshot bajo lock. Cargas concurrentes son seguras.

**Patrón decorador puro:** elegido (Decisión 2 del kickoff 1C) porque funciona idéntico contra Django, SQLAlchemy, Pydantic, dataclasses, NamedTuple, o plain class. Cero acoplamiento a herencia.

---

## 5. Fases de Desarrollo

Cada fase tiene **objetivo, entregables, criterios de aceptación y Definition of Done (DoD)**. **No se pasa a la siguiente fase sin DoD verde.**

### Fase 0 — Cimientos del Repositorio ✅ COMPLETADA

Cerrada el 2026-05-13 con tag `v0.0.1-alpha.0` en commit `b6262c6`. Documento de cierre: `PHASE_0_CLOSURE.md`. Detalles en `CHANGELOG.md`.

---

### Fase 1 — Núcleo ✅ COMPLETADA

Cerrada el 2026-05-14 con tag `v0.1.0-alpha` en commit `fd8ee2d`. Documento de cierre consolidado: `PHASE_1_CLOSURE.md`. Detalles en `CHANGELOG.md`.

Tres sub-fases consolidadas:

| Sub-fase | Tag | Commit | Entregables |
|---|---|---|---|
| 1A | `v0.0.2-alpha.0` | `909d32d` | Identity (`TenantId`), exceptions (10 clases), context (sync + async) |
| 1B | `v0.0.3-alpha.0` | `02667b8` | Audit bus (events, sinks, SINK_FAILURE handling), Policy engine (sealed Decision, 3 built-in policies, `evaluate_and_audit`) |
| 1C | `v0.1.0-alpha` | `fd8ee2d` | ModelRegistry (class + default + decorator), mkdocs scaffold, ADR-0001, bench.yml workflow, version bump |

**Resumen consolidado:**

- Superficie pública: **44 nombres** en `tenantshield.__all__`. Contrato estable para Fase 2+.
- Tests: **141 passing** + 2 smoke benchmarks deselected por default.
- Cobertura: **100% líneas, 100% ramas** en los 7 módulos productivos.
- Stmts productivos: **314**. Branches productivas: **32**.
- Toolchain: ruff, mypy strict, pyright strict, bandit, pip-audit, pre-commit, mkdocs strict — todos verdes.
- Dependencias: **77 resueltas, 0 vulnerabilidades activas**.
- Decision Records acumulados al cierre: **12 (DR-001 a DR-012)**.

---

### Fase 2 — Adapter Django + DRF

**Objetivo:** Enforcement total sobre Django ORM y DRF. Primer adapter de framework — momento donde TenantShield deja de ser "motor puro Python" y se convierte en "motor + integración con ecosistema real".

**Estado actual:** Sub-fase 2A cerrada (`v0.2.0-alpha.0`, commit `9671ebb`, 2026-05-14). Sub-fase 2B siguiente. Descomposición ratificada en el kickoff de Fase 2 (2A → 2B → 2C).

**Sub-fase 2A — Django ORM enforcement core.** **Status: closed at v0.2.0-alpha.0 (commit 9671ebb, 2026-05-14).** See `PHASE_2A_CLOSURE.md` for full closure documentation. Sub-phase 2B (middleware + tenant extraction) is the next focus.

**Descomposición ratificada:**

- **2A — Django ORM enforcement core.** TenantAwareManager/QuerySet, integración con `register_model`, validación de coherencia tenant en `pre_save`/`pre_delete`, detector de cross-tenant joins. **Cerrada.**
- **2B — Middleware + extracción de tenant.** `TenantContextMiddleware` configurable (subdomain, header, JWT claim, callable). Integración con ciclo request/response.
- **2C — DRF integration.** ViewSet mixin, permission class `IsSameTenant`, serializer hooks. Ejemplo runnable en `examples/01_django/`. Cierre de Fase 2 completa; tag `v0.2.0-alpha`.

**Entregables consolidados:**

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
- **Matriz multi-versión activa**: Python 3.11/3.12/3.13 × Django 4.2/5.x. Resuelve deuda histórica desde Fase 0.
- Tests de regresión que reproducen los 5 patrones clásicos de leak (lista en `docs/concepts/known-leaks.md` a redactar en Fase 2).
- Bench: overhead de filtrado < 5% sobre query baseline.
- `mypy --strict` pasa con `django-stubs` configurado.
- DRF browsable API funcional en `examples/01_django/`.

**DoD:** Tag `v0.2.0-alpha`. Aplicación demo desplegada en `examples/01_django/` con README de uso. Documento de cierre `PHASE_2_CLOSURE.md`.

**Prerrequisitos antes del kickoff de Fase 2:**

1. Roadmap v1.4 commiteado (este documento) — resuelve enmiendas E20-E23 y registra DR-012.
2. Workflow `docs.yml` alineado con `ci.yml`/`bench.yml`/`security.yml` (resolución E22, commit independiente con prefijo `ci:`).
3. Dry-run del Tech Lead sobre kickoff de Fase 2 cubriendo: descomposición (2A/2B/2C vs monolítico), estructura del adapter Django, integración con `register_model`, matriz CI multi-versión, testcontainers o pytest-django, scope del primer ejemplo runnable.

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

> **Nota:** según §6 #10, **antes** del tag `v0.5.0-alpha`, el owner configura su llave de signing local y se empieza a firmar commits. Los commits previos no se reescriben. ADR-0001 documenta formalmente esta decisión.

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
- Documentación completa, incluida guía de migración desde `django-tenants` / scoped manual. Esto incluye expansión profunda de los conceptos hoy en scaffold (Sub-fase 1C entregó scaffold mínimo; Fase 8 entrega profundidad).
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
10. **Commits firmados (SSH/GPG/sigstore) a partir de v0.5.0-alpha**, una vez el owner configure su llave de signing local. Los commits previos no se reescriben para firmarse retroactivamente. ADR-0001 (materializado en Sub-fase 1C) documenta formalmente esta decisión.
11. **Reviewer ≠ Autor.** En este proyecto: yo (tech lead chat) reviso lo que ejecuta Claude Code.
12. **CHANGELOG actualizado en cada PR** bajo `[Unreleased]`.
13. **Atribución exclusiva al owner.** Ningún artefacto del proyecto (commit, PR, issue, documentación, metadatos del paquete) acredita herramientas de IA. La regla aplica a Claude, Copilot, Cursor, Aider, o cualquier otra asistencia automatizada presente o futura. La política pública se codifica en `CONTRIBUTING.md` §Attribution.
14. **Falsos positivos de linters: se excluyen archivos, no se silencian reglas.** Si una regla legítima dispara sobre contenido no-código (documentación legacy en otro idioma, datos de prueba, ejemplos), el archivo se excluye explícitamente en la config de la herramienta. Silenciar la regla globalmente está prohibido salvo justificación documentada en un ADR.
15. **Reportes de BLOCKER por CVE.** Cuando un BLOCKER es por CVE, el reporte inicial debe incluir, como mínimo: ID de la CVE, severidad cualitativa o CVSS, vector de ataque, `fix_versions`, y aplicabilidad al contexto de uso del proyecto. Sin esos cinco campos, el Tech Lead no puede decidir sin pedir información adicional y la iteración se duplica.
16. **Bumps en cadena por mitigación de CVE.** Cuando la remediación de una CVE implica forced upgrades transitivos, cada bump debe pasar por *changelog review cualitativo* antes de aplicarse, no solo verificación de resolución de dependencias.
17. **Verificación per-file con `--no-cov`.** El primer comando de verificación per-tarea (`pytest <file> -v`) incluye `--no-cov` cuando el gate global `--cov-fail-under=95` está activo. La verificación de cobertura es responsabilidad exclusiva del comando final per-módulo (`pytest --cov=<module> --cov-report=term-missing`).
18. **Context managers usan `Generator`/`AsyncGenerator`, no `Iterator`/`AsyncIterator`.** El typeshed actual marca `Iterator[T]` como tipo de retorno de `@contextmanager` como deprecated. Las firmas canónicas son `Generator[T, None, None]` y `AsyncGenerator[T, None]`.
19. **Conventional Commits exige veracidad descriptiva.** Cuando una tarea se aparta del kickoff por enmienda autorizada, el commit message refleja la realidad post-enmienda, no el contenido literal del kickoff. Cuando un commit toca múltiples áreas (e.g. `docs/` + `.github/workflows/`), se separa en commits independientes con prefijos coherentes (`docs:` vs `ci:`).
20. **Criterios de Hypothesis: `failing` no `invalid`.** La métrica de validación de propiedades es `0 failing examples`, no `0 invalid examples`. `invalid` es métrica de eficiencia de generación, no de calidad.
21. **El kickoff manda sobre el GO message.** Cuando un mensaje de GO del Tech Lead generaliza un criterio que el kickoff trata de forma específica, el kickoff manda.
22. **Specs literales pasan filtro de imports usados.** Cuando el Tech Lead dicta contenido literal de un archivo, debe verificar que cada import declarado se usa al menos una vez en el cuerpo. F401 detecta imports muertos; emitirlos en una spec es fallo del Tech Lead.
23. **Tests de propiedades inestables usan techo catastrófico, no budget estricto.** Cuando una métrica varía significativamente entre runs en el mismo hardware por jitter del sistema, el test enforce un techo catastrófico (eg. 50x el peor caso observado) y deja los budgets estrictos para CI ephemeral aislado. Patrón canónico: env var `*_STRICT=1` selecciona budget estricto en CI; default usa techo catastrófico.
24. **`try/except/pass` → `contextlib.suppress(<ExcType>)` siempre.** Ruff SIM105 dispara cuando `try/except/pass` cubre una sola excepción específica. `contextlib.suppress` es el patrón canónico moderno: comunica intención explícitamente y elimina simultáneamente SIM105 y S110 (que dispara sobre `pass`).
25. **`Union[X, Y, Z]` → `X | Y | Z` por defecto (PEP 604).** En proyectos con target Python 3.10+ y toolchain moderno, la forma `|` es funcionalmente equivalente a `typing.Union` para todos los usos relevantes y permite además `isinstance(x, MyAlias)` directo.
26. **Consolidaciones que afectan dependencias se materializan en `pyproject.toml` en el mismo commit.** Si una consolidación de fase registra un DR que menciona una dep nueva, el commit que registra el DR también añade la dep al manifest. Evita el gap roadmap/manifest documentado en E10.
27. **Specs literales del Tech Lead usan ASCII puro.** Docstrings y mensajes que el ejecutor copia textualmente a archivos son ASCII puro. Caracteres Unicode "tipográficos" (`×`, `—`, `…`, etc.) disparan RUF002/RUF003.
28. **`# pragma: no cover` legítimo en Protocol stubs y `assert_never` branches.** Dos casos: cuerpos `...` de métodos en `Protocol` clases (contrato, no implementación) y `case _: assert_never(d)` al final de un `match` exhaustivo (defensivo, debe ser inalcanzable en valid typing).
29. **`@dataclass(frozen=True, slots=True)` sobre clases sin campos: quitar `slots=True`.** Bug conocido en CPython (lineage de `bpo-44806`, presente en 3.13.13 verificado empíricamente). El `__setattr__` generado falla con `TypeError` en lugar de `FrozenInstanceError`. Para clases marker sin campos, `frozen=True` se mantiene, `slots=True` se omite. Cuando los campos existen, `slots=True` se conserva.
30. **Imports en tests/fixtures van top-level salvo ciclo estructural verificado empíricamente.** PLC0415 dispara sobre imports inline ornamentales. Tests no participan en grafos de import circular del paquete porque no son importados por nada. La regla "imports al top de archivo" aplica sin excepción en tests.
31. **Precisiones del Tech Lead deben ser internamente consistentes.** Cuando una Precisión referencia un patrón ("idéntico al de X") y simultáneamente dicta un snippet, ambos deben coincidir. Si hay divergencia, el ejecutor aplica el patrón referenciado (X manda) y reporta la inconsistencia. La referencia explícita gana sobre el snippet inline. Para specs futuras: revisar dos veces que los snippets dictados textualmente coincidan con los patrones referenciados.
32. **Versiones de dependencias se verifican antes de pinear, usando la fuente canónica por ecosistema (revisada en v1.5).** PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`) para paquetes Python; `gh release view` para herramientas distribuidas vía GitHub Releases (actions, CLIs); el registry del package manager correspondiente para otros ecosistemas. El filtro de estabilidad >2 semanas aplica a la fuente canónica, no a duplicados o espejos. Declaraciones factuales del Tech Lead sobre el estado del ecosistema externo ("X no existe aún", "X está en versión Y", "X tiene LTS hasta Z") disparan la misma verificación que los pins; memoria sin verificación es obsoleta por construcción.
33. **Workflows de GitHub Actions son internamente consistentes.** Los workflows del proyecto comparten versiones de actions (`@v6` para checkout, `@v8` para setup-uv, etc.) y patrones de setup (cache, python install). Cuando se añade un workflow nuevo, antes de commitear se verifica que sus versiones de actions coinciden con los existentes (`ci.yml` es la referencia canónica). Inconsistencia entre workflows del mismo proyecto es deuda explícita que se resuelve en la siguiente consolidación.
34. **Precisiones del Tech Lead deben referenciar patrones coherentemente con decisiones y precedentes previos.** Nuevas Precisiones que contradicen un precedente sin justificación disparan BLOCKER analítico para resolución.
35. **Declaraciones factuales del Tech Lead sobre estado del ecosistema externo requieren verificación.** Versión disponible, estado LTS, historial de release, comportamiento de framework — todos requieren confirmación contra la fuente canónica o test empírico antes de fijarse en specs. Aserciones desde memoria son no-fiables por construcción.
36. **Precisiones que prescriben orden verifican el estado actual del archivo objetivo antes de afirmar el orden nuevo.** Prescribir cambios que entran en conflicto con patrones intencionales preexistentes es BLOCKER trivial.
37. **Specs que retrasan tests para módulos productivos deben anticipar el efecto del gate global de cobertura en commits intermedios.** Si una spec crea código productivo sin tests a lo largo de tareas N..M y añade tests solo en M+1, la spec debe incluir el mecanismo de exclusión (omit list con comentario que documente la tarea de reversión) en la tarea N, no descubrirlo como BLOCKER a media ejecución.
38. **Thresholds numéricos sobre noqa o type-ignore en Precisiones son heurísticas, no contratos.** Señalan auto-revisión y escalada a BLOCKER cuando se superan significativamente. Cuando el contexto (framework externo, limitación de stubs upstream, patrón canónico del ecosistema) justifica superar el threshold con cada entrada documentada arquitectónicamente en comentarios adyacentes, el threshold se supera tras discusión explícita de trade-off. La categorización por causa raíz importa más que el conteo absoluto.
39. **Verificación de aplicación, no solo de importabilidad.** Cuando una tarea entrega un decorator, mixin, monkey-patch, o componente que modifica el comportamiento de una clase de framework externo, la verificación per-tarea debe incluir test empírico de aplicación contra el framework real: instanciar o aplicar el componente, ejercitar al menos un read y un write donde aplique, y verificar empíricamente la propiedad esperada (`type(Decorated.attribute).__name__`, inspección de comportamiento end-to-end). La importabilidad confirma que el código existe; la aplicación confirma que hace lo que su spec dice. Para adapters Django: cargar settings, decorar un modelo, correr un read y un write dentro de `tenant_scope`. Procedimientos equivalentes aplican a SQLAlchemy (Fase 3), Celery (Fase 4), y cualquier adapter futuro. Tres bugs arquitectónicos en Sub-fase 2A (commits `578652c`, `97db7f2`, `52f15ee`) fueron causados por violaciones de esta regla; la regla se añade retroactivamente para prevenir recurrencia.
40. **Smoke scripts son specs sujetas a §6 #39.** Smoke scripts producidos por el Tech Lead durante un kickoff están sujetos a la misma verificación empírica que el código productivo. El smoke debe ejecutar verde antes de ratificar el kickoff o iniciar la primera tarea. Bugs en el script son bugs de spec: BLOCKER inmediato + reporte, sin improvisar fix. Cada smoke script debe ser self-contained re-execution environment: `sys.path` setup explícito vía `__file__` resolution, `DJANGO_SETTINGS_MODULE` env var declarada, settings overrides runtime (`ALLOWED_HOSTS = ["*"]`, etc.) si `DEBUG=False`. Patrón canónico documentado en `docs/evidence/smoke_*.md` por sub-fase. (Origen: E37, manifestado retrospectivamente en pre-2B.0 con 2 fixes acumulados al script del kickoff §0.2.)
41. **Dependency extras se añaden vía PEP 621, no PEP 735.** Añadir optional extras al proyecto se hace editando manualmente `[project.optional-dependencies]` en `pyproject.toml` + `uv sync --all-extras --dev`, **NO** con `uv add --pkg <extra>` ni `uv add --dev`. `uv add --dev` crea sección PEP 735 `[dependency-groups]` separada del extra histórico, divergencia silenciosa al schema PEP 621 que el proyecto usa desde Fase 0. Además, `uv remove --dev <pkg>` puede dejar `[dependency-groups].dev = []` vacío que uv interpreta como "sin dev deps", causando desinstalación masiva del venv en la próxima sync. Recovery vía `git checkout pyproject.toml uv.lock && uv sync --all-extras --dev`. (Origen: E38, validado en pre-2B.0 + Tarea 2B.1.)
42. **Tests de Django middleware usan `Client(raise_request_exception=False)`.** Tests integration de Django middleware vía `django.test.Client` deben construir el Client con `Client(raise_request_exception=False)` para que excepciones del middleware se traduzcan a HTTP 500 en `response.status_code`, no se propaguen al test code. Default `raise_request_exception=True` está diseñado para que tests de Django-application (views) puedan capturar errores con `assertRaises`, pero rompe el contrato HTTP-shape esperado por tests de middleware: el cliente real ve códigos HTTP, no excepciones Python. Patrón canónico: tests de middleware usan `Client(raise_request_exception=False)` + aserciones sobre `response.status_code`; tests específicos que quieran inspeccionar la excepción interna usan `Client()` default + `assertRaises`. (Origen: E40, manifestado en pre-2B.7 BLOCKER trivial.)
43. **`@override_settings` class-level requiere `SimpleTestCase`.** `@override_settings` aplicado a clase en tests pytest plain classes **NO funciona**; Django lo soporta solo en `SimpleTestCase` subclasses. Patrón canónico para pytest sin herencia Django: (a) `@override_settings(...)` a nivel method individual, o (b) `with override_settings(...):` block dentro del test body. Si los settings se repiten entre tests, extraer a constantes module-level y aplicar decorator/with-block consumiendo la constante. (Origen: E41, manifestado en Tarea 2B.9 con fix mecánico de `@override_settings` class-level → method-level.)
44. **Closure transcripts archivan task commit hashes por sub-phase.** Cada `PHASE_<sub-phase>_CLOSURE.md` enumera explícitamente los commits hashes de cada tarea atómica de la sub-fase (e.g., `2B.0 → 0d4f43e`, `2B.1 → 887cf5c`, etc.) bajo sección "Atomic tasks". Esta trazabilidad permite navegación `git show <hash>` retrospectiva sin requerir reconstrucción del orden. Los closure docs son gitignored vía glob `PHASE_*_CLOSURE.md` (local-only). (Origen: práctica consolidada en Sub-fases 1C, 2A, 2B; formalizada como regla en consolidación post-2B.)

---

## 6a. Datapoints Técnicos (referencia, no enforceable)

Los siguientes items emergieron durante Sub-fase 2A como referencias técnicas para implementaciones futuras. No son reglas enforceables sino contexto útil para patrones similares en fases venideras.

**Datapoint E28** — Decorators con tres formas de uso (`@d`, `@d(...)`, `d(Cls)`) requieren overloads con `/` (positional-only marker) consistente entre overloads cuando el primer parámetro es positional-only. mypy diagnostica inconsistencia con `[misc] Overloaded function implementation does not accept all possible arguments of signature N`. Relevante para decorators del adapter Fase 3 (SQLAlchemy) — patrones análogos probables.

**Datapoint E29** — Ruff trata acceso a `_meta` distinto según el tipo del receptor. Con `model: type` (genérico), ruff diagnostica `SLF001`. Con `model: type[django.db.models.Model]` (parametrizado), ruff reconoce la declaración de django-stubs de `_meta` como public-by-contract y no diagnostica. Narrow el tipo lo antes posible tras entry para reducir overhead de noqa.

**Datapoint E32** — `git -c tag.gpgSign=false tag -a ...` defensivo para operaciones de tag. Confirmado como no-op en el entorno actual pero protege contra cambios futuros de configuración global. Mismo patrón aplica cuando el commit signing se enforce sistemáticamente (diferido a `v0.5.0-alpha` per ADR-0001).

**Datapoint E33** — El escape hatch `_unscoped` en el adapter Django es read-only por arquitectura. Los signal handlers (`pre_save`, `pre_delete`) se conectan al model class, no al manager; por lo tanto `_unscoped` bypasea el filtering del manager (read path) pero NO bypasea la validation de signals (write path). Documentar en `docs/concepts/known-leaks.md` al cierre de Fase 2.

**Datapoint E34** — Inspección de receivers de Django signals requiere examinar contenido, no longitud. `Signal._live_receivers(sender=Model)` retorna tupla `(receivers, async_receivers)` — dos listas. `len(...)` naive siempre retorna 2. Para asserts "sin receivers conectados", verificar que ambas sub-listas estén vacías.

**Datapoint E35** — Django models pueden declararse inline dentro de funciones test cuando `Meta.app_label` apunta a una app de `INSTALLED_APPS`. Útil para modelos efímeros que ejercitan código que itera sobre el registry de Django models (system checks, registry walkers) sin contaminar el testapp permanente. Cleanup vía `try/finally + default_registry.unregister(...)` previene contaminación entre tests.

**Datapoint E39** — Anotación explícita `: object` habilita narrowing `isinstance`. Para narrowing `isinstance` sobre valores `getattr(obj, attr, default) or fallback`, anotar el target var explícitamente como `object` permite que `isinstance` narrows correctamente sin necesidad de `cast()`. Sin la anotación, pyright infiere `Any | dict[Unknown, Unknown]` (o similar union con `Unknown`) que el `isinstance` check no narrows limpiamente. Aplicable a system checks, configuration parsing, y cualquier código que lee de settings/config dicts con fallbacks. Manifestado en Tarea 2B.6 sobre `raw_config` en `check_middleware_strategy_configured` y `check_public_tenant_mode_visible`.

**Datapoint E42** — PyJWT HMAC key length warning. PyJWT 2.x emite warning informativa cuando el secret HMAC tiene <32 bytes para HS256 (RFC 7518 §3.2). Tests que ejercitan `JWTStrategy` con secrets sintéticos deben usar ≥32 bytes para evitar warning noise en suite de tests. Constante reutilizable: `_TEST_JWT_SECRET = "test-secret-32-bytes-or-longer-for-hs256-key"` (47 bytes). En producción, los secrets son generados por operadores con tamaño adecuado, no necesita validación adicional en el adapter. Manifestado en Tarea 2B.4 + consolidado patrón en 2B.8.

**Datapoint E43** — Coverage gaps en defensive branches. System checks con early returns defensivos (e.g., `if not isinstance(config, Mapping): return []`, `if not list(default_registry): return []`) pueden no quedar cubiertos por el set inicial de tests happy/edge. Patrón canónico: incluir explícitamente un test por branch defensiva. `monkeypatch.setattr` es la herramienta para estados inalcanzables por settings normales (e.g., `default_registry` vacío). Manifestado en Tarea 2B.9 con dos tests adicionales para W001 non-dict bypass + W002 empty registry, llevando `checks.py` de 94.37% a 100% líneas.

---

## 7. Flujo de Trabajo entre Tech Lead y Claude Code

Para cada fase o sub-fase:

1. **Tech Lead** (chat) realiza *spec validation by dry-run* del kickoff antes de emitirlo. El dry-run cubre: (a) viabilidad del código que se escribe; (b) viabilidad de cómo lo verifica el toolchain con su config real, ejecutando mentalmente cada comando contra los plugins activos; (c) filtro de imports usados (regla §6 #22); (d) verificación empírica de ciclos cuando se prescribe deferred imports (con `python -c "import X"` antes de fijar la spec); (e) verificación de qué reglas de ruff disparan sobre cada patrón con la config actual; (f) consistencia interna entre referencias a patrones y snippets dictados (regla §6 #31); (g) versiones actuales de tooling auxiliar verificadas externamente (regla §6 #32).
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

Fase 1 cerrada. **Consolidación post-Fase 1 en curso:**

1. **Roadmap v1.4** (este documento) — registrado DR-012, aplicadas enmiendas E20-E23 como reglas §6 #31-#33 y refinamientos §7.
2. **CHANGELOG.md** — DR-012 registrado bajo `[Unreleased] → Decision Records`.
3. **Workflow `docs.yml`** — bumpeado a versiones consistentes con `ci.yml`/`bench.yml`/`security.yml` (resuelve E22). Commit independiente con prefijo `ci:`.

Tras consolidación, **pausa profunda — cadencia γ extendida** antes de Fase 2.

Cuando el owner confirme disponibilidad para arrancar Fase 2, el Tech Lead realiza dry-run cubriendo:

- Descomposición de Fase 2 en sub-fases 2A/2B/2C vs ejecución monolítica.
- Estructura del adapter Django: `apps.py`, `managers.py`, `signals.py`, `middleware.py`.
- Integración inicial de `django-stubs` con `mypy --strict`.
- Matriz CI multi-versión: Python 3.11/3.12/3.13 × Django 4.2/5.x.
- Decisión sobre testcontainers vs pytest-django para integration tests.
- Strategy para tests de regresión sobre los 5 patrones clásicos de leak (lista a redactar como `docs/concepts/known-leaks.md` durante Fase 2).
- Interacción de `register_model` decorator con `models.Model` (multiple inheritance considerations).
- Cómo `tenant_scope` interactúa con el ciclo request/response de Django.
- Scope mínimo del primer ejemplo runnable en `examples/01_django/`.

---

## 10. Historial de revisiones

| Versión | Fecha | Tag al momento | Cambios |
|---|---|---|---|
| 1.0 | 2026-05-13 (inicio Fase 0) | — | Versión inicial. |
| 1.1 | 2026-05-13 (cierre Fase 0) | `v0.0.1-alpha.0` | Consolidación post-Fase 0: §6 #13/#14/#15/#16 nuevos, §6 #10 enmendado, §4.3 TenantId NewType (DR-009), §5 Fase 1 descompuesta (DR-008), §7 *spec validation by dry-run*. |
| 1.2 | 2026-05-14 (cierre Sub-fase 1A) | `v0.0.2-alpha.0` | Consolidación post-Sub-fase 1A: §2 `structlog` añadido a stack (DR-010), §3 `bench.yml` previsto, §4.1 sinks built-in actualizados, §4.2 `structlog` como dep base documentada, §4.4 jerarquía marcada como implementada, §5 Sub-fase 1A marcada como ✅ con tag y resumen, §5 Sub-fase 1B refinada, §5 Sub-fase 1C con bump de versión explícito, §6 nuevas reglas #17-#23, §7 BLOCKER trivial vs analítico + verificación de autofixes + coherencia top-level. |
| 1.3 | 2026-05-14 (cierre Sub-fase 1B) | `v0.0.3-alpha.0` | Consolidación post-Sub-fase 1B: §2 `structlog` zero-dep confirmado, §3 `bench.yml` movido a Sub-fase 1C, `conftest.py` global notado, §4.1 diagrama actualizado con audit bus completo + SINK_FAILURE handling, §4.2 decisión sealed-por-convención formalizada, §4.5 NUEVO modelo de decisiones de Policy con DR-011, §5 Sub-fase 1B marcada como ✅, §5 Sub-fase 1C refinada, §6 nuevas reglas #24-#30, §7 dry-run expandido, tests modelan al usuario. |
| 1.4 | 2026-05-14 (cierre Fase 1) | `v0.1.0-alpha` | Consolidación post-Fase 1: §3 todos los entregables de Fase 1 marcados ✅, §4.6 NUEVO ModelRegistry como decisión arquitectónica (DR-012), §5 Fase 1 marcada como ✅ COMPLETADA con tabla consolidada de las tres sub-fases, §5 Fase 2 refinada con descomposición tentativa 2A/2B/2C y prerrequisitos explícitos, §6 nuevas reglas #31 (Precisiones internamente consistentes, E20), #32 (versiones de tooling auxiliar verificadas, E21), #33 (workflows internamente consistentes, E22), §6 #19 reforzado con separación de concerns en commits, §6 #23 ampliado con patrón env var `*_STRICT`, §7 dry-run expandido con consistencia interna (f) y versiones de tooling (g), §9 próximo paso inmediato actualizado para reflejar consolidación en curso y pausa γ pre-Fase 2. |
| 1.5 | 2026-05-14 (cierre Sub-fase 2A) | `v0.2.0-alpha.0` | Consolidación post-Sub-fase 2A: §5 Fase 2 status actualizado con Sub-fase 2A cerrada y descomposición ratificada, §6 #32 reformulada (PyPI JSON API canónico, E24/E25), §6 nuevas reglas #34-#39 absorbiendo E20/E25/E26/E27/E30/E31 refined, §6a NUEVA sección con datapoints técnicos E28/E29/E32/E33/E34/E35 (no enforceable). ADR-0002 (Django 6.0 deferral) materializado en `docs/adr/0002-django-6-deferral.md`. CHANGELOG promovido a `[0.2.0-alpha.0]` con DR-013/014/015 + 3 bug fixes documentados. |
| 1.6 | 2026-05-15 (cierre Sub-fase 2B) | `v0.2.0-alpha.1` | Consolidación post-Sub-fase 2B: §6 nuevas reglas #40-#44 absorbiendo E37/E38/E40/E41 + formalización de práctica closure transcripts (Rule 44), §6a datapoints E39/E42/E43 añadidos, §11 NUEVA sección "Deferred Items" con DPRJ-2 (resolve_strategy KeyError vs ImproperlyConfigured). Sin cambios a CHANGELOG (DR-016/017/018 ya promovidas en commit `28e00f7` durante Tarea 2B.11, divergencia de patrón vs post-2A — patrón 2B preferible por trazabilidad del tag). |

---

## 11. Deferred Items

Items diferidos que no bloquean el siguiente milestone pero requieren atención en una fase o sub-fase futura. Cada entry incluye contexto, scope estimado, y opciones de resolución.

**DPRJ-2 — `resolve_strategy()` raises `KeyError` for missing `jwt_secret` instead of `ImproperlyConfigured`.** El kickoff §4.4 de Sub-fase 2B dictó la traducción a `ImproperlyConfigured` (Django idiom) pero la implementación simplificó a acceso directo `config["jwt_secret"]`. Tests adaptados a `KeyError` expectation en Tarea 2B.8 (Issue B). El comportamiento es correcto (config inválida levanta excepción), solo el tipo de excepción es no-idiomático Django.

- **Fix candidates:** (a) commit `fix:` dedicado durante Sub-phase 2C refinamiento de error messages para DRF integration, o (b) bundled en Phase 2 closure consolidation en Tarea 2C.N.
- **Estimated effort:** ~10 líneas (wrap `config["jwt_secret"]` en try/except + `ImproperlyConfigured` re-raise) + 1 test update.
- **Origen:** Tarea 2B.8 closure observation.
- **Status:** non-blocking; documentado para resolución en 2C o post-2B.

---

*Fin del documento.*
