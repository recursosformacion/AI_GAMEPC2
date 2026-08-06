# Jobs — Diseño (V2.2.c)

> **Status: draft** (iteración 2 — se congelará antes de la implementación de V2.2.c).
>
> Parte de V2.2. Define la infraestructura para ejecutar tareas de larga duración de
> forma programada o bajo demanda. No se escribe código hasta congelar este diseño.

## Principio rector

> **Un Job nunca contiene reglas de negocio. Solo orquesta procesos ya existentes.**

Toda decisión de negocio sigue viviendo en `Canonicalizer`, `Matcher`, `Ranking`,
`Merge` y `Evidence`. El Job únicamente decide **cuándo** ejecutar un proceso, nunca
**cómo** resolverlo.

## 1. Objetivo

V2.2.c introduce la infraestructura necesaria para ejecutar tareas de larga duración.
Ejemplos:

- actualizar proveedores
- reconstruir índices
- recalcular rankings
- sincronizar catálogos
- limpiar cachés
- importar nuevos datos

## 2. Posición en la arquitectura

```
          HTTP / CLI
               │
               ▼
        Application Services
               │
        ┌──────┴───────┐
        │              │
     búsquedas       Jobs
        │              │
        ▼              ▼
  Dominio V2.1     Dominio V2.x
```

**Los Jobs nunca llaman directamente a proveedores.** Siempre usan
**Application Services**. Un Job puede combinar varios servicios ya existentes; nunca
implementa su propia lógica de proveedor ni de dominio.

## 3. Scheduler (fuera del alcance)

Los Jobs no conocen cómo son ejecutados. Pueden ser lanzados desde:

- CLI
- API
- Cron
- APScheduler
- Celery
- Worker propio

El scheduler pertenece **exclusivamente a infraestructura**. El contrato del Job
permanece **idéntico** independientemente del mecanismo de ejecución. Es la misma
filosofía que usamos con los Providers.

## 4. Qué es (y qué no es) un Job

Un **Job** representa una **unidad de trabajo ejecutable**.

- No representa un hilo.
- No representa una tarea del sistema operativo.
- No representa un cron.
- Es simplemente una **operación larga**.

## 5. Contrato principal — `IJob`

### `IJob`

Responsabilidad: `run(context) -> JobResult`.

Propiedades:
- **puro respecto al dominio** (no acopla el dominio a la infraestructura);
- **idempotente** cuando sea posible (re-ejecutar produce el mismo estado final);
- **cancelable** (puede detenerse de forma cooperativa);
- **observable** (produce eventos).

### `JobContext`

Contiene **únicamente información de ejecución**. No contiene reglas de negocio.

```
execution_id      # identificador único de esta ejecución
started_at        # marca de inicio
triggered_by      # origen (schedule, api, cli, test)
dry_run           # ejecuta sin efectos secundarios (validación)
options           # opciones específicas del job (tipadas por job)
```

### `JobResult`

Tipado de la misma forma que `MatchResult` / `RankingResult` (Value Object inmutable):

```python
@dataclass(frozen=True)
class JobResult:
    status: JobStatus
    duration: timedelta
    processed_count: int
    skipped_count: int
    failed_count: int
    errors: tuple[JobError, ...]
```

`JobError` es un error **estructurado y tipado** (p. ej. `code`, `field`, `context`),
no una cadena libre.

### `JobStatus`

Enum:

```
PENDING
RUNNING
COMPLETED
FAILED
CANCELLED
```

### `JobDefinition` y `JobExecution` (idea, sin implementar)

Hoy solo existe el Job. Normalmente también existe una **definición**:

- `ProviderSyncJob` es una **definición** (`JobDefinition`).
- Cada ejecución genera una **ejecución** (`JobExecution`).

Eso permite **histórico, reintentos, monitorización y estadísticas** sin tocar el
contrato `IJob`. **No se implementa nada en V2.2.c**: solo se deja preparada la idea.

## 6. Tipos de Job (iniciales)

Inicialmente:

- `ProviderSyncJob`
- `ReindexJob`
- `CacheCleanupJob`
- `StatisticsJob`

**No todos se implementan en V2.2.c.** V2.2.c solo prepara la **arquitectura**: el
contrato `IJob`, `JobContext`, `JobResult`, `JobStatus`, la observabilidad por eventos y
un caso de uso de referencia. Los jobs concretos se materializan cuando el scheduler se
decida.

## 7. Observabilidad

Todos los Jobs producen **eventos tipados**, igual que Evidence:

```python
class JobEventType(Enum):
    STARTED
    PROGRESS
    FINISHED
    FAILED


@dataclass(frozen=True)
class JobEvent:
    type: JobEventType
    execution_id: str
    timestamp: datetime
    payload: object   # tipado según el tipo de evento
```

**No escriben logs directamente.** Los logs son infraestructura. El Job emite eventos;
la infraestructura decide si persistirlos, registrarlos o exponerlos.

## 8. Errores

Los errores **no abortan necesariamente** el Job. Cada Job decide:

- **continuar**
- **reintentar**
- **cancelar**

La **política** (cuántos reintentos, backoff, tolerancia) pertenece a **infraestructura**,
no al propio Job.

## 9. ¿Qué NO hace un Job?

Un Job **no**:

- contiene lógica de Merge
- contiene lógica del Matcher
- contiene lógica del Ranker
- modifica `WorkDescriptor`
- conoce APIs de proveedor
- genera HTML
- usa IA

Todo eso lo delega en los procesos ya existentes (vía Application Services) o en otros
módulos.

## 10. Criterios de aceptación (V2.2.c)

- **contratos congelados** antes de implementar
- Jobs **desacoplados del dominio**
- **idempotencia definida**
- `JobResult` completamente tipado
- `JobStatus` como `Enum`
- **observabilidad** mediante eventos
- tests **deterministas**
- **sin modificar el núcleo** V2.0 / V2.1 / V2.2 (a ni b)

## 11. Nota de alcance (recomendación)

A diferencia de V2.2.a y V2.2.b, **este documento no crecerá mucho más**. Los Jobs
pertenecen claramente a la **infraestructura**, no al corazón del dominio. Modelarlos con
el mismo nivel de detalle que el Matcher o el Merge arriesga **sobrearquitectura** en una
parte que probablemente cambie al decidir un scheduler concreto (Celery, APScheduler,
cron, workers propios, etc.).

Este diseño se mantiene en **3–5 páginas centradas en contratos y responsabilidades**.
El esfuerzo de diseño detallado se reserva para **V2.2.d (Knowledge Mining)**, que vuelve
a ser una pieza de **dominio**.
