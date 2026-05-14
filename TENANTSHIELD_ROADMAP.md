# TenantShield — Plan Maestro de Desarrollo

> **Documento de gobierno técnico del proyecto.**
> Autoridad: Tech Lead (sesión de chat).
> Ejecutor: Claude Code Console.
> Estado: v1.1 — Consolidación post-Fase 0.
> Última revisión: 2026-05-13.
> Tag de proyecto al revisar: `v0.0.1-alpha.0` (Fase 0 cerrada).

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
│       ├── context.py             # sub-fase 1A
│       ├── exceptions.py          # sub-fase 1A
│       ├── policies.py            # sub-fase 1B
│       ├── audit.py               # sub-fase 1B
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
                └──────────────────────────────────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  │                               │
        ┌─────────▼────────┐            ┌─────────▼─────────┐
        │  Policy Engine   │            │   Audit Bus       │
        │  - DenyByDefault │            │  - StructuredLog  │
        │  - AllowList     │            │  - Metrics        │
        │  - Custom        │            │  - Hooks          │
        └─────────┬────────┘            └───────────────────┘
                  │
   ┌──────────────┼──────────────┬─────────────────┐
   │              │              │                 │
┌──▼───┐    ┌─────▼─────┐   ┌────▼────┐      ┌─────▼─────┐
│Django│    │SQLAlchemy │   │ Celery  │      │   DRF     │
│Adapt.│    │ Adapter   │   │ Adapter │      │  Adapter  │
└──────┘    └───────────┘   └─────────┘      └───────────┘
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
- **Sin import-time side effects.** Importar `tenantshield` no monkey-patchea nada. El usuario activa los adapters explícitamente.
- **Event bus síncrono y predecible.** No usamos un sistema pub/sub asíncrono por defecto; los eventos se emiten en línea y los sinks son responsables de no bloquear.

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

**Por qué no las alternativas:**

- **`TenantId = str` directo:** pierde la pista del tipo en revisión de código. `def f(x: str)` vs `def f(x: TenantId)` envían señales muy distintas al lector.
- **`TenantId = TypeVar`:** propaga genericidad por toda la API, infectando 50+ firmas con `[TenantIdT]`. Coste de ergonomía mayor que el beneficio.
- **`TenantId` como clase Pydantic / dataclass:** introduce dependencia de runtime y serialización custom. Innecesario para un identificador.

### 4.4 Jerarquía de excepciones (obligatoria)

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

Cada excepción transporta los siguientes campos estructurados (frozen dataclass o slots):

- `tenant_id_expected: TenantId | None`
- `tenant_id_actual: TenantId | None`
- `model: str | None` (nombre completo del modelo: `"app.MyModel"`)
- `operation: str` (categoría: `"read"`, `"write"`, `"delete"`, etc.)
- `stack_context: Mapping[str, object]` (datos auxiliares para debugging)

Todas las excepciones se serializan a un dict reproducible vía `to_dict()` para uso en auditoría.

---

## 5. Fases de Desarrollo

Cada fase tiene **objetivo, entregables, criterios de aceptación y Definition of Done (DoD)**. **No se pasa a la siguiente fase sin DoD verde.**

### Fase 0 — Cimientos del Repositorio ✅ COMPLETADA

Cerrada el 2026-05-13 con tag `v0.0.1-alpha.0` en commit `b6262c6`. Documento de cierre: `PHASE_0_CLOSURE.md`. Detalles en `CHANGELOG.md`.

---

### Fase 1 — Núcleo (descompuesta en tres sub-fases)

**Justificación de la descomposición (DR-008):** Fase 1 original era demasiado grande para tratarse como unidad operativa. Se descompone en tres sub-fases con entregables verificables independientes, cada una con su propio kickoff, sus propios criterios de aceptación, y su propio cierre.

---

#### Sub-fase 1A — Identidad y excepciones

**Objetivo:** establecer el sustrato de identidad de tenant y la jerarquía completa de errores tipados. Sin esto, ninguna sub-fase posterior puede empezar.

**Entregables:**

- `tenantshield.exceptions`:
  - Jerarquía completa según §4.4.
  - Frozen dataclasses con campos estructurados.
  - `to_dict()` reproducible en cada clase.
  - Cada excepción cubierta por tests directos.
- `tenantshield.context`:
  - `TenantId = NewType("TenantId", str)` exportado públicamente.
  - `TenantContext` (frozen dataclass): `tenant_id: TenantId`, `metadata: Mapping[str, object]`.
  - `current_tenant() -> TenantContext` (raises `MissingTenantContextError`).
  - `try_current_tenant() -> TenantContext | None`.
  - `tenant_scope(ctx: TenantContext)` context manager (sync y async, vía `contextlib.contextmanager` + `contextlib.asynccontextmanager`).
  - `bind_tenant(tenant_id: TenantId, **metadata: object)` helper de conveniencia.
  - `__all__` explícito declarando la superficie pública.
- Tests:
  - Unit tests por excepción y por cada función de `context`.
  - Property-based tests con `hypothesis` para anidamiento de scopes (al menos 3 niveles).
  - Tests específicos de propagación async: `asyncio.create_task`, `asyncio.gather`, `asyncio.TaskGroup`, `asyncio.to_thread`.
  - Tests de aislamiento entre threads concurrentes.

**Criterios de aceptación:**

- 100% cobertura de líneas en `exceptions.py` y `context.py`.
- Cobertura de ramas ≥ 95% en ambos.
- `mypy --strict` y `pyright strict` cero issues.
- Benchmark: entrar y salir de `tenant_scope` < 1µs en Python 3.13 (mediana sobre 10.000 iteraciones).
- Tests property-based corren ≥ 100 ejemplos por propiedad sin fallar.
- Documentación de cada función pública con docstring estilo Google.

**DoD:** Tag `v0.0.2-alpha.0` aplicado. Documento de cierre de sub-fase 1A análogo a `PHASE_0_CLOSURE.md`.

---

#### Sub-fase 1B — Políticas y auditoría

**Objetivo:** motor de decisión sobre operaciones tenant-aware + bus de eventos de auditoría. Depende exclusivamente de 1A.

**Entregables:**

- `tenantshield.policies`:
  - `Policy` Protocol: `evaluate(operation: Operation) -> Decision`.
  - `Operation` dataclass: encapsula `model`, `operation_type` (read/write/delete), `tenant_context`, `extras`.
  - `Decision` sealed type: `Allow`, `Deny(reason: str)`, `RequireScope(filter_spec: FilterSpec)`.
  - `DenyByDefaultPolicy` (default global).
  - `AllowListPolicy(allowed_models: Set[str])`.
  - Composición: `ChainPolicy([p1, p2, ...])` aplica políticas en orden, primer `Deny` gana.
- `tenantshield.audit`:
  - `AuditEvent` (frozen dataclass tipado): `timestamp`, `event_type`, `tenant_context`, `payload`.
  - `AuditEventType` Enum: `POLICY_ALLOW`, `POLICY_DENY`, `CONTEXT_BOUND`, `CONTEXT_RELEASED`, `ENFORCEMENT_VIOLATION`.
  - `AuditSink` Protocol: `emit(event: AuditEvent) -> None`.
  - Sinks built-in: `StructLogSink`, `NullSink`, `InMemorySink` (último para tests).
  - `emit(event: AuditEvent)`: thread- y async-safe, despacha a todos los sinks registrados.
  - `register_sink(sink: AuditSink)` / `unregister_sink(sink: AuditSink)`.
  - Tolerancia a fallos: un sink que lanza excepción no interrumpe a los demás; se emite un `AuditEvent` interno de tipo `SINK_FAILURE`.
- Integración:
  - Las políticas, cuando deniegan, emiten automáticamente un `AuditEvent` de tipo `POLICY_DENY`.
  - `tenant_scope` emite `CONTEXT_BOUND` y `CONTEXT_RELEASED`.

**Criterios de aceptación:**

- 100% cobertura de líneas, ≥ 95% ramas en `policies.py` y `audit.py`.
- `mypy --strict` y `pyright strict` cero issues.
- Tests property-based para composición de políticas.
- Test de "sink que falla no rompe el bus" verificado.
- Benchmark: `emit()` con 3 sinks < 10µs en Python 3.13.

**DoD:** Tag `v0.0.3-alpha.0` aplicado. Documento de cierre de sub-fase 1B.

---

#### Sub-fase 1C — Registro y documentación

**Objetivo:** cerrar el núcleo de Fase 1 con el registro de modelos tenant-aware y montar la infraestructura de documentación que el proyecto necesita para escalar.

**Entregables:**

- `tenantshield.registry`:
  - `ModelRegistry`: registro tipado de modelos tenant-aware.
  - `register_model(model: type, tenant_field: str = "tenant_id")` decorador y función.
  - `is_tenant_aware(model: type) -> bool`.
  - `get_tenant_field(model: type) -> str`.
  - Descubrimiento opcional vía marker class `TenantAware` o decorador.
  - Aislamiento por aplicación: dos proyectos importando TenantShield no comparten registro.
- Infraestructura `docs/`:
  - `docs/index.md`, `docs/getting-started.md`, `docs/concepts/`, `docs/adapters/` (placeholder), `docs/api/` (autogenerada).
  - `docs/adr/0001-commit-signing-deferral.md` — materializa DR-003 como ADR formal.
  - `mkdocs.yml` con tema Material y plugin `mkdocstrings`.
- Workflow:
  - `.github/workflows/docs.yml`: build de docs en cada PR, deploy a GitHub Pages en push a `main`.
- Actualización del `pyproject.toml`:
  - `mkdocs-material` y `mkdocstrings[python]` añadidos al extra `dev`.

**Criterios de aceptación:**

- 100% cobertura de líneas en `registry.py`.
- `mkdocs build --strict` pasa sin warnings.
- Documentación generada incluye API reference completa de `context`, `exceptions`, `policies`, `audit`, `registry`.
- ADR-0001 escrito y revisado.

**DoD:** Tag `v0.1.0-alpha` aplicado. **Cierra Fase 1 completa.** Documento de cierre de Fase 1 consolidado.

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
9. **Sin `# type: ignore` sin código de error específico y comentario.**
10. **Commits firmados (SSH/GPG/sigstore) a partir de v0.5.0-alpha**, una vez el owner configure su llave de signing local. Los commits previos no se reescriben para firmarse retroactivamente. ADR-0001 (materializado en sub-fase 1C) documenta formalmente esta decisión.
11. **Reviewer ≠ Autor.** En este proyecto: yo (tech lead chat) reviso lo que ejecuta Claude Code.
12. **CHANGELOG actualizado en cada PR** bajo `[Unreleased]`.
13. **Atribución exclusiva al owner.** Ningún artefacto del proyecto (commit, PR, issue, documentación, metadatos del paquete) acredita herramientas de IA. La regla aplica a Claude, Copilot, Cursor, Aider, o cualquier otra asistencia automatizada presente o futura. La política pública se codifica en `CONTRIBUTING.md` §Attribution.
14. **Falsos positivos de linters: se excluyen archivos, no se silencian reglas.** Si una regla legítima dispara sobre contenido no-código (documentación legacy en otro idioma, datos de prueba, ejemplos), el archivo se excluye explícitamente en la config de la herramienta. Silenciar la regla globalmente está prohibido salvo justificación documentada en un ADR.
15. **Reportes de BLOCKER por CVE.** Cuando un BLOCKER es por CVE, el reporte inicial debe incluir, como mínimo: ID de la CVE, severidad cualitativa o CVSS, vector de ataque, `fix_versions`, y aplicabilidad al contexto de uso del proyecto. Sin esos cinco campos, el Tech Lead no puede decidir sin pedir información adicional y la iteración se duplica.
16. **Bumps en cadena por mitigación de CVE.** Cuando la remediación de una CVE implica forced upgrades transitivos, cada bump debe pasar por *changelog review cualitativo* antes de aplicarse, no solo verificación de resolución de dependencias. La pregunta "¿uv resuelve sin conflicto?" es necesaria pero no suficiente; debe complementarse con "¿el comportamiento del paquete cambia de formas que afecten nuestro código actual o planeado?".

---

## 7. Flujo de Trabajo entre Tech Lead y Claude Code

Para cada fase o sub-fase:

1. **Tech Lead** (chat) realiza *spec validation by dry-run* del kickoff antes de emitirlo. Esta práctica es obligatoria desde sub-fase 1A en adelante, lección registrada tras los cuatro BLOCKERs encadenados de Tarea 0.2.
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

Fase 0 cerrada. **Sub-fase 1A en preparación.**

El siguiente paso operativo es la emisión del `PHASE_1A_KICKOFF.md` por parte del Tech Lead, con dry-run aplicado. Cuando el owner confirme su disponibilidad para arrancar 1A, el Tech Lead emite el kickoff y Claude Code propone el plan de implementación detallado antes de la primera tarea atómica.

---

## 10. Historial de revisiones

| Versión | Fecha | Tag al momento | Cambios |
|---|---|---|---|
| 1.0 | 2026-05-13 (inicio Fase 0) | — | Versión inicial. |
| 1.1 | 2026-05-13 (cierre Fase 0) | `v0.0.1-alpha.0` | Consolidación post-Fase 0: enmiendas §6 #10 (signing diferido) y §6 #13/#14/#15/#16 (nuevas reglas), §4.3 nueva (TenantId como NewType, DR-009), §5 Fase 1 descompuesta en sub-fases 1A/1B/1C (DR-008), §7 actualizado con *spec validation by dry-run* y adaptaciones técnicas autorizadas, §3 con anotaciones de en qué fase se materializa cada componente. |

---

*Fin del documento.*
