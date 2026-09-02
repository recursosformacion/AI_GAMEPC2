# ADR-0014 – Modelo de identidad musical (Work → Edition → Arrangement → Score)

## Estado

Aceptado.

> **Nota de evolución (sept 2026):** la decisión de pipeline modular (ADRs 0014-0017)
> es histórica. En la implementación actual `PipelineEngine` fue **eliminado** por estar
> huérfano; el circuito vigente de adquisición/validación es:
> `resolve_session()` → `AcquisitionService` → `BestRepresentationSelector` →
> `ScoreValidationStage` → `BasicValidator` → `MusicXmlValidator`.

## Contexto

Hasta ahora `CandidateRepresentation`/`WorkDescriptor` no distinguían entre una
obra, una edición, un arreglo y una representación concreta. Eso impedía, por
ejemplo, asociar un MusicXML de OpenScore, un MusicXML de Audiveris y un PDF
original a la misma obra con su edición y arreglo.

## Decisión

Se establece la jerarquía:

```
MusicalWork
    └── Edition
            └── Arrangement
                    └── Score
```

- `Edition`: publicación concreta (editorial, año, editor).
- `Arrangement`: arreglo concreto (voces, instrumentación, arreglista).
- `Score`: representación concreta (formato, proveedor, calidad).

## Consecuencias

- Distingue obra / edición / arreglo / representación.
- `DuplicateResolver` usa esta identidad para decidir si dos representaciones
  pertenecen a la misma obra (sin depender del proveedor).
- El frontend puede mostrar `/works/{id}` con la jerarquía completa.

---

# ADR-0015 – Pipeline modular y Event Bus

## Contexto

El pipeline crecía con pasos acoplados; añadir o quitar una etapa requería tocar
el motor.

## Decisión

- **Pipeline modular**: cada etapa es un plugin (`IPipelineStage`:
  `LookupStage`, `DatasetStage`, `DownloadStage`, `OmrStage`, `MergeStage`,
  `ValidationStage`, `LibraryStage`). El `PipelineEngine` las compone
  dinámicamente (`add_stage`/`run`). Añadir/eliminar etapas no modifica el motor.
- **Event Bus**: `IEventBus` publica `ProviderStarted/Finished/Failed`,
  `DatasetInstalled/Updated`, `ScoreValidated`, `ScoreMerged`, `LibraryStored`,
  `Job*`, `Stage*`. Estos eventos alimentan la UI React, la barra de progreso,
  el monitor, los logs y un futuro WebSocket.

## Consecuencias

- Open/Closed: el pipeline se extiende registrando etapas y suscriptores.
- El frontend refleja el progreso sin conocer infraestructura.

---

# ADR-0016 – Job Engine (procesamiento asíncrono)

## Contexto

Operaciones largas (descargar 40 GB, OMR, merge, generar) bloquearían la
interfaz si fueran síncronas.

## Decisión

Se introduce el concepto de **`Job`** (id, type, state, progress, logs,
started_at, finished_at, result) con estados `pending/running/completed/failed/
cancelled`, gestionado por `IJobRunner`. Las operaciones largas devuelven un
`Job`; la UI muestra cola, progreso, cancelación y notificaciones.

## Consecuencias

- La API REST devuelve `202 { job_id, type, state }` para operaciones largas.
- `InMemoryJobEngine` es la implementación de referencia; puede sustituirse por
  una cola real sin cambiar el contrato.

---

# ADR-0017 – Quality Model multidimensional

## Contexto

Un único valor de confianza no era suficiente para que Chorus decidiera qué
materiales generar.

## Decisión

Se sustituye por un **`QualityReport`** que puntúa dimensiones independientes
(Structure, Notation, Lyrics, Harmony, Voices, Metadata, Attachments) en [0, 1],
del que se deriva un `QualityLevel` (Unreadable, Partial Structure, Basic
Melody, Full Notation, Human Validated).

## Consecuencias

- Chorus decide los materiales en función del nivel de calidad.
- El ranking y la Knowledge Base consumen el informe por dimensiones.
