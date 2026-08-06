# ADR-0028 – API REST de OSAP (V3.1) — contrato

## Estado

Aceptado. Congela el contrato de la API REST (`v3.1.a`), antes de la implementación
(V3.1.b).

## Principios

- **La API no implementa lógica**: expone casos de uso del dominio ya existentes, vía
  Application Services.
- **La API nunca expone componentes internos**: ni Matcher, ni Ranking, ni Merge, ni
  Canonicalizer, ni Evidence, ni KnowledgeCollector/Miner. Habla el lenguaje del usuario.
- **OpenAPI es el contrato oficial** de la API (generado automáticamente, no a mano).
- **Estabilidad del contrato**: los contratos REST son API pública; la evolución es solo
  *backward compatible*; los cambios incompatibles requieren `/api/v2` y un ADR.
- **`request_id` obligatorio** en todas las respuestas.

## Contexto

El dominio de OSAP está completo (V2.2, `v2.2.0`). V3 lo expone. La decisión estratégica
central es tratar la búsqueda como un **recurso** (`/searches`) y no como un simple
`POST /search`, para soportar estados futuros (QUEUED/RUNNING/COMPLETED/FAILED) sin
cambiar la API.

## Decisión

- **Base URL versionada**: `/api/v1/` desde el primer día; nunca `/api/search`.
- **Recursos principales** (nada más al inicio):
  - `POST /api/v1/searches` (→ `201` + `Location`) y `GET /api/v1/searches/{id}`.
  - `GET/POST /api/v1/jobs` y `GET /api/v1/jobs/{id}`.
  - `GET /api/v1/knowledge/{observations,facts,suggestions}` — solo lectura; `POST`
    prohibido.
  - `GET /api/v1/providers` y `GET /api/v1/providers/{id}`, `{id}/status`.
  - `GET /api/v1/system/{health,ready,live,version,statistics}`.
- **DTO públicos tipados** (`SearchRequest`, `SearchResponse`, `JobResponse`,
  `ProviderResponse`, `KnowledgeResponse`, `SystemResponse`, `ErrorResponse`),
  **independientes del modelo de dominio** (no se reutilizan los Value Objects internos).
- **Respuesta uniforme**: `success` + `request_id` + `data`, o `success` + `request_id` +
  `error{code,message,details}`.
- **Auth** preparada (`Bearer`) y **deshabilitada** en V3.1.

## Consecuencias

- La API es estable y evoluciona sin romper consumidores.
- Un cambio en el dominio (p. ej. `WorkDescriptor`) no rompe `SearchResponse` (DTOs
  independientes).
- El framework (FastAPI) es infraestructura sustituible, desacoplado del contrato.
- Las búsquedas pueden volverse asíncronas/distribuidas en el futuro sin cambiar el
  contrato (recurso `/searches/{id}`).
