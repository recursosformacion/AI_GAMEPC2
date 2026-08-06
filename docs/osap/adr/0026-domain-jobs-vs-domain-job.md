# ADR-0026 – `domain.jobs` (V2.2) frente a `domain.job` (legado)

## Estado

Aceptado. Documenta la coexistencia tras la implementación de V2.2.c.

## Principios

- **`domain.jobs` es la arquitectura de Jobs de V2.2** (el modelo del diseño
  `docs/osap/v2/jobs-design.md`): `IJob`, `JobContext`, `JobResult`, `JobStatus`,
  `JobEvent*`.
- **`domain.job` es compatibilidad con el runtime legado** (el `InMemoryJobEngine` de
  V2.0): `Job`, `JobResult`, `JobState`, `JobSubmission`.
- Ambos conviven **sin romper contratos congelados**; `domain.job` no se toca.
- No se implementan scheduler, persistencia ni historial hasta que se decida el
  runtime de ejecución.

## Contexto

V2.2.c introduce un modelo de Jobs nuevo (`domain.jobs`) que **colisiona en el nombre**
con el `JobResult` ya existente en `domain.job`. `domain.job` está en uso por el runtime
legado (`InMemoryJobEngine`, `app.py`, `ports/job_runner.py`) y exporta `JobResult` en
`domain/__init__.py`. Cambiarlo rompería ese contrato V2.0.

## Decisión

- El nuevo modelo vive en **`domain.jobs`** y es la dirección futura.
- El nuevo `JobResult` (V2.2) **no se re-exporta** en `domain/__init__.py` (el nombre ya
  lo ocupa el legado); se importa vía `src.osap.domain.jobs`.
- **`domain.job` se mantiene tal cual** como compatibilidad con el runtime legado,
  con la intención de **retirarse en una limpieza mayor futura**, no ahora.

## Consecuencias

- Quien consuma Jobs debe importar de `domain.jobs` (nuevo) en lugar de `domain.job`.
- `domain/__init__.py` exporta los tipos nuevos de `domain.jobs` **excepto** `JobResult`,
  para no romper el `JobResult` legado.
- Una futura limpieza mayor deberá retirar `domain.job`, `JobResult` legado e
  `InMemoryJobEngine` y re-exportar el `JobResult` de V2.2 en el paquete raíz.
