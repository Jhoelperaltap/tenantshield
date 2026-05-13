# TenantShield — Plan Maestro de Desarrollo

> **Documento de gobierno técnico del proyecto.**
> Autoridad: Tech Lead (Claude, sesión de chat).
> Ejecutor: Claude Code Console.
> Estado: v1.0 — Línea base aprobada.
> Última revisión: 2026-05-13.

Este documento define **qué se construye, cómo se construye, con qué calidad y en qué orden**. Cualquier desviación requiere justificación técnica documentada en el `CHANGELOG.md` bajo la sección `Decision Records`. No se acepta "lo hice así porque era más rápido". El código que no cumple los estándares de este documento **no entra a `main`**.

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
| Python máximo CI | **3.13** | Última estable. |
| Gestor de paquetes | **`uv`** | Velocidad, lockfile reproducible, gestión de toolchain. |
| Build backend | **`hatchling`** | PEP 517/621 limpio, sin Setuptools legacy. |
| Linter + formatter | **`ruff` + `ruff format`** | Sustituye flake8/isort/black; rapidísimo. |
| Type checking | **`mypy --strict`** (gate) + **`pyright`** (segunda opinión en CI) | Doble red de seguridad. |
| Tests | **`pytest`**, **`pytest-asyncio`**, **`pytest-cov`**, **`hypothesis`** | Estándar de facto + property-based. |
| Cobertura mínima | **95% líneas, 90% ramas** | No es decorativo: el CI falla por debajo. |
| Seguridad estática | **`bandit`**, **`pip-audit`**, **`semgrep`** | Tres ángulos diferentes. |
| Docs | **`mkdocs-material`** + **`mkdocstrings`** | Generación desde docstrings tipados. |
| Versionado | **SemVer 2.0.0** | Sin atajos. |
| Mensajes de commit | **Conventional Commits** | Habilita changelog automático. |
| CI | **GitHub Actions**, matriz `{3.11, 3.12, 3.13} × {django 4.2, 5.x} × {sqlalchemy 2.x}` | |
| Licencia | **Apache-2.0** | Permisiva con cláusula de patentes; apta para enterprise. |
| Distribución | **PyPI** vía Trusted Publishing (OIDC, sin tokens) | |

Cualquier propuesta de cambio sobre esta tabla se debate en un *Architecture Decision Record* (`docs/adr/NNNN-titulo.md`) antes de implementarse.

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
├── .editorconfig
├── .pre-commit-config.yaml
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── release.yml
│   │   ├── security.yml
│   │   └── docs.yml
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
├── docs/
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
│       ├── context.py             # TenantContext, ContextVar, scoping
│       ├── exceptions.py          # Jerarquía completa de errores
│       ├── policies.py            # Deny/Allow/Custom policies
│       ├── audit.py               # Event bus + sinks
│       ├── analyzer.py            # Query analyzer estático y runtime
│       ├── registry.py            # Registro de modelos tenant-aware
│       ├── config.py              # Settings tipados (pydantic-free, dataclasses)
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py            # Protocolo Adapter
│       │   ├── django/
│       │   │   ├── __init__.py
│       │   │   ├── apps.py
│       │   │   ├── managers.py
│       │   │   ├── middleware.py
│       │   │   ├── signals.py
│       │   │   └── drf.py
│       │   ├── sqlalchemy/
│       │   │   ├── __init__.py
│       │   │   ├── events.py
│       │   │   ├── filters.py
│       │   │   └── session.py
│       │   └── celery/
│       │       ├── __init__.py
│       │       └── signals.py
│       ├── asyncio/
│       │   ├── __init__.py
│       │   └── propagation.py
│       └── testing/
│           ├── __init__.py
│           ├── fixtures.py
│           ├── factories.py
│           └── generator.py       # Auto test generator
└── tests/
    ├── unit/
    ├── integration/
    │   ├── django/
    │   ├── sqlalchemy/
    │   └── celery/
    └── e2e/
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

### 4.3 Jerarquía de excepciones (obligatoria)

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

Cada excepción transporta: `tenant_id_expected`, `tenant_id_actual`, `model`, `operation`, `stack_context`.

---

## 5. Fases de Desarrollo

Cada fase tiene **objetivo, entregables, criterios de aceptación y Definition of Done (DoD)**. **No se pasa a la siguiente fase sin DoD verde.**

### Fase 0 — Cimientos del Repositorio

**Objetivo:** Repositorio listo para escribir código de producción con todos los guardarraíles activos.

**Entregables:**
- `pyproject.toml` con metadata completa, extras definidos, classifiers, URLs.
- Configuración de `ruff`, `mypy`, `pytest`, `coverage` en `pyproject.toml`.
- `.pre-commit-config.yaml` con: ruff, ruff-format, mypy, bandit, check-yaml, check-toml, end-of-file-fixer, trailing-whitespace, debug-statements, codespell.
- `.github/workflows/ci.yml` con lint + typecheck + test matrix + coverage gate.
- `.github/workflows/security.yml` con `pip-audit` + `bandit` + `semgrep`.
- `LICENSE` (Apache-2.0), `README.md` (esqueleto), `CHANGELOG.md` (formato Keep a Changelog), `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`.
- `src/tenantshield/__init__.py` con `__version__`, `__all__` vacío explícito, y `py.typed` marker.
- `tests/` con un test placeholder que verifica que el paquete importa.

**Criterios de aceptación:**
- `uv sync --all-extras --dev` completa sin error.
- `pre-commit run --all-files` pasa.
- `pytest` pasa.
- `mypy src/` pasa con `--strict`.
- `ruff check .` pasa con cero violaciones.
- El CI corre verde en un PR de prueba.

**DoD:** Tag `v0.0.1-alpha.0` aplicado al commit del cierre de fase.

---

### Fase 1 — Núcleo: Contexto, Políticas, Auditoría

**Objetivo:** Construir el corazón del sistema, **agnóstico a cualquier ORM**.

**Entregables:**
- `tenantshield.context`:
  - `TenantContext` (frozen dataclass): `tenant_id: TenantId`, `metadata: Mapping[str, object]`.
  - `current_tenant() -> TenantContext` (raises `MissingTenantContextError`).
  - `try_current_tenant() -> TenantContext | None`.
  - `tenant_scope(ctx: TenantContext)` context manager (sync y async).
  - `bind_tenant(...)` helper para frameworks.
  - Cobertura completa de propagación a `asyncio.create_task` y `concurrent.futures`.
- `tenantshield.policies`:
  - `Policy` Protocol: `evaluate(operation: Operation) -> Decision`.
  - `DenyByDefaultPolicy` (default).
  - `AllowListPolicy`.
  - Decisiones: `Allow`, `Deny(reason)`, `RequireScope(filter_spec)`.
- `tenantshield.audit`:
  - `AuditEvent` (dataclass tipado).
  - `AuditSink` Protocol.
  - Sinks built-in: `StructLogSink`, `NullSink`, `InMemorySink` (para tests).
  - `emit(event: AuditEvent)` thread- y async-safe.
- `tenantshield.exceptions`: jerarquía completa documentada.
- `tenantshield.registry`:
  - `ModelRegistry` para registrar qué modelos son tenant-aware y bajo qué campo (`tenant_id` por defecto, configurable).
  - Detección por declaración explícita **y** por descubrimiento opcional (marker class / decorator).

**Criterios de aceptación:**
- 100% cobertura de líneas en `context.py`, `policies.py`, `audit.py`, `exceptions.py`, `registry.py`.
- Tests property-based con `hypothesis` para anidamiento de scopes.
- Tests específicos de propagación async (incluyendo `TaskGroup`, `gather`, `to_thread`).
- Benchmark: entrar y salir de `tenant_scope` < 1µs en Python 3.12.
- Documentación de API generada y revisada manualmente.

**DoD:** Tag `v0.1.0-alpha`. Demo runnable en `examples/00_core/`.

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

**DoD:** Tag `v0.2.0-alpha`. Aplicación demo deployada en `examples/01_django/` con README de uso.

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

**Criterios de aceptación:**
- El analizador estático corre sobre el propio repositorio en CI y reporta 0 issues.
- Tests con corpus de "código malo conocido" — debe detectar el 100%.

**DoD:** Tag `v0.5.0-alpha`.

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
10. **Commits firmados (GPG/sigstore).**
11. **Reviewer ≠ Autor.** En este proyecto: yo (tech lead chat) reviso lo que ejecuta Claude Code.
12. **CHANGELOG actualizado en cada PR** bajo `[Unreleased]`.

---

## 7. Flujo de Trabajo entre Tech Lead y Claude Code

Para cada fase:

1. **Tech Lead** (yo) emite la instrucción de inicio de fase referenciando este documento.
2. **Claude Code** propone un *plan de implementación detallado* (lista de archivos, firmas de funciones clave, riesgos identificados).
3. **Tech Lead** aprueba, corrige o rechaza el plan.
4. **Claude Code** implementa **una tarea a la vez**, no la fase completa de golpe.
5. Tras cada tarea: ejecutar `pre-commit`, `pytest`, `mypy`, `ruff`. Reportar resultado completo.
6. **Tech Lead** valida contra criterios de aceptación.
7. Solo cuando todos los criterios están verdes, se cierra la fase con su tag.

**Reglas para Claude Code:**

- No avanzar a la siguiente tarea sin confirmación si surge ambigüedad.
- No introducir dependencias no listadas en la tabla de stack sin pedir aprobación.
- No silenciar errores de lint/type. Si surge, escalarlo.
- No "limpiar" código no relacionado con la tarea en curso.
- Si algo de este documento parece estar mal, **señalarlo antes de actuar**, no improvisar.

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

Cuando me confirmes que apruebas este documento (o me indiques qué cambiar), arrancamos la **Fase 0**. La primera instrucción a Claude Code será generar el esqueleto del repositorio con `pyproject.toml`, configuración de herramientas y CI mínima, y validar que todo el toolchain corre verde antes de escribir una sola línea de lógica de negocio.

No escribimos código de producto hasta tener los guardarraíles puestos. Esa no es una preferencia: es la regla.

---

*Fin del documento. Firmado: Tech Lead.*
