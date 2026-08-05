# OSAP — Job Engine

Operaciones largas (descargar un dataset de 40 GB, ejecutar Audiveris, consultar
proveedores, fusionar, generar materiales) **no deben bloquear la interfaz**.

## Concepto de Job

```
Job
 ├── id
 ├── type
 ├── state        (pending | running | completed | failed | cancelled)
 ├── progress     (0..100)
 ├── logs
 ├── started_at
 ├── finished_at
 └── result
```

`IJobRunner` (`infrastructure/jobs/InMemoryJobEngine`) ejecuta los `Job` en un
hilo de fondo, transita los estados y publica eventos (`JobSubmitted`,
`JobStarted`, `JobCompleted`, `JobFailed`, `JobCancelled`).

## Integración

- **REST**: `POST /resolve` devuelve `202 { job_id, type, state }`; `GET /jobs/{id}`
  da el progreso; `POST /jobs/{id}/cancel` cancela.
- **Frontend React**: cola de trabajos, barras de progreso, cancelación y
  notificaciones vía `/events` (WebSocket/SSE).
- **Pipeline**: cada etapa puede ejecutarse dentro de un `Job`; el `PipelineEngine`
  compone etapas y publica `Stage*` en el EventBus.

`InMemoryJobEngine` es una implementación de referencia; puede sustituirse por
una cola real (Celery/RQ) sin cambiar el contrato.
