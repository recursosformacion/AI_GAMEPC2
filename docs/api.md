# OSAP 1.0 — API REST (contrato)

## Congelación del contrato

A partir de la versión 1.0 (documento aprobado):

- **No se modifican** entidades del dominio, interfaces públicas, DTOs ni el
  contrato REST aquí descrito, salvo para corregir errores demostrables.
- Las mejoras futuras se implementan mediante **nuevos servicios o adaptadores**,
  preservando la compatibilidad del backend con esta API y con el frontend React.
- Cambios incompatibles requieren una nueva versión (`/api/v2`).

## Títulos: display vs canónico

La normalización se usa **exclusivamente para comparar obras**, nunca para
mostrar información. Cada obra conserva tres campos:

| Campo             | Uso                                            |
|-------------------|------------------------------------------------|
| `display_title`   | Título visible al usuario (el mejor disponible). Nunca es salida de un normalizador. |
| `canonical_title` | Título normalizado, solo para comparación/agrupación interna. |
| `canonical_key`   | Clave interna estable de la obra (comparación). |

`title` en `WorkDTO` equivale a `display_title`. La API nunca expone la clave
canónica como título de presentación.

## Dominio público (tri-estado)

`public_domain` en las respuestas admite tres valores:

| Valor          | Significado                                   |
|----------------|-----------------------------------------------|
| `true`         | Sí                                            |
| `false`        | No                                            |
| `null`         | Desconocido (nunca se deduce "No" por ausencia de información) |

## La API REST (contrato)

La API REST está implementada en `src/osap/api/app.py` y expone el mismo
dominio. El frontend React consume exclusivamente esta API, nunca
infraestructura.

## Versionado

Toda la API pública vive bajo `/api/v1/`.

```
/api/v1/works ...
/api/v1/resolve
...
```

Alternativa soportada: header `Accept: application/vnd.osap.v1+json` (el
cliente puede omitirlo y usar el prefijo de ruta, que es más sencillo para
React).

## Recursos de primer nivel

Cada nivel de la jerarquía de identidad musical se expone como recurso
independiente, para que React no tenga que recorrer el árbol en consultas
sencillas.

| Recurso                | Método(s)                        | Descripción                                          |
|------------------------|----------------------------------|------------------------------------------------------|
| `/works`               | GET, GET `/{id}`                 | Obras musicales                                      |
| `/editions`            | GET `?publisher=Carus&year=2001` | Ediciones                                            |
| `/arrangements`        | GET `?voices=SATB`               | Arreglos                                             |
| `/scores`              | GET `?quality=full-notation`     | Representaciones concretas (filtrable por calidad)   |

```json
GET /api/v1/scores?quality=full-notation
→ { "scores": [ { "id": "sc1", "title": "Ave Maria", "provider": "openscore", ... } ] }

GET /api/v1/arrangements?voices=SATB
→ { "arrangements": [ { "id": "a1", "voices": ["S","A","T","B"], ... } ] }

GET /api/v1/editions?publisher=Carus
→ { "editions": [ { "id": "e1", "publisher": "Carus", "year": 2001, ... } ] }
```

## Resolución y búsqueda

| Recurso       | Método | Descripción                                    |
|---------------|--------|------------------------------------------------|
| `/resolve`    | POST   | Resuelve una obra (crea un Job)                |
| `/search`     | GET    | Búsqueda tolerante de obras                    |
| `/ranking`    | POST   | Devuelve ranking con motivo (utilidad: depuración) |

```json
POST /api/v1/resolve
{
  "query": "Ave Maria",
  "composer": "Bruckner",
  "format": "musicxml",
  "voices": ["SATB"]
}
→ 202 { "job_id": "job_123", "type": "resolve", "state": "running" }

POST /api/v1/ranking
{
  "query": "Die Sterne",
  "composer": "Schubert"
}
→ {
  "ranking": [
    { "provider": "openscore", "score": 0.91, "reason": "MusicXML, CC0, local availability" },
    { "provider": "pdmx",      "score": 0.88, "reason": "MusicXML, public domain, requires install" },
    { "provider": "imslp",     "score": 0.43, "reason": "PDF only, online, connectivity error" }
  ]
}
```

## Quality Report

Expuesto como recurso, no implícito. Chorus decide qué materiales generar
según el `QualityLevel` y las dimensiones.

```json
GET /api/v1/scores/sc1/quality
→ {
  "level": "basic-melody",
  "dimensions": {
    "structure":   0.98,
    "notation":    0.81,
    "lyrics":      0.35,
    "harmony":     0.62,
    "voices":      0.95,
    "metadata":    0.70,
    "attachments": 0.00
  }
}
```

## Merge

El `MergeEngine` es recurso de primera clase. Entrada: varios Scores; salida:
un Job que produce el Score fusionado.

```json
POST /api/v1/merge
{
  "sources": ["sc1", "sc2", "sc3"]
}
→ 202 { "job_id": "job_merge_456", "type": "merge", "state": "running" }
```

## Duplicate Resolver

Determina si dos representaciones son la misma obra, con motivo y porcentaje
de equivalencia.

```json
POST /api/v1/duplicates
{
  "first":  "sc1",
  "second": "sc2"
}
→ {
  "equivalent": true,
  "confidence": 0.85,
  "reasons": [
    "identical title after normalization",
    "matching composer",
    "same checksum"
  ]
}
```

## Knowledge Base

No oculta; expuesta como recurso para consulta y aprendizaje.

| Recurso                         | Método | Descripción                                   |
|---------------------------------|--------|-----------------------------------------------|
| `/knowledge/providers`          | GET    | Estadísticas agregadas por proveedor          |
| `/knowledge/statistics`         | GET    | Estadísticas globales                         |
| `/knowledge/work/{id}`          | GET    | Historial de resoluciones para una obra       |

```json
GET /api/v1/knowledge/providers
→ {
  "providers": [
    { "provider": "openscore", "success_rate": 0.94, "avg_time_s": 3.2, "most_frequent_quality": "full_notation" },
    { "provider": "imslp",     "success_rate": 0.67, "avg_time_s": 12.1, "most_frequent_quality": "partial_structure" }
  ]
}
```

## Pipeline

Devuelve el grafo de etapas con estado, orden y configuración. **Imprescindible**
para depuración y administración.

```json
GET /api/v1/pipeline
→ {
  "stages": [
    { "name": "Lookup",   "enabled": true,  "order": 1, "config": { "timeout": 20 } },
    { "name": "Dataset",  "enabled": true,  "order": 2, "config": { "streaming": false } },
    { "name": "Download", "enabled": true,  "order": 3, "config": {} },
    { "name": "Validation","enabled": true, "order": 4, "config": { "strict": false } },
    { "name": "Merge",    "enabled": false, "order": 5, "config": {} },
    { "name": "Library",  "enabled": true,  "order": 6, "config": { "target": "local" } }
  ]
}
```

## Observabilidad

| Recurso       | Método | Descripción                                                    |
|---------------|--------|----------------------------------------------------------------|
| `/health`     | GET    | Estado de proveedores, datasets, jobs, memoria, knowledge base |
| `/monitor`    | GET    | Dashboard en tiempo real (providers, datasets, CPU, RAM, cache)|
| `/statistics` | GET    | Agregados: nº obras, scores, descargas, datasets, éxito, tiempo|
| `/logs`       | GET    | Historial de eventos y operaciones                              |
| `/logs/jobs`  | GET    | Logs por job                                                    |
| `/logs/providers` | GET | Logs por proveedor                                              |

```json
GET /api/v1/health
→ {
  "openscore":  "OK",
  "pdmx":       "Installed",
  "imslp":      "Unreachable",
  "knowledge":  "OK",
  "jobs":       "2 running"
}

GET /api/v1/monitor
→ {
  "providers": { "openscore": "ok", "imslp": "error" },
  "datasets":  { "pdmx": "not_installed" },
  "jobs":      { "running": 2, "pending": 1 },
  "cache":     { "entries": 42, "size_mb": 128 },
  "system":    { "cpu_pct": 23, "ram_mb": 512 }
}

GET /api/v1/statistics
→ {
  "works":      1520,
  "scores":     4800,
  "downloads":  920,
  "datasets":   2,
  "top_provider": "openscore",
  "success_rate_by_provider": { "openscore": 0.94, "imslp": 0.67 },
  "avg_resolution_time_s": 4.2
}
```

## Jobs

Toda operación larga devuelve un `Job`. El frontend escucha `/events`
(WebSocket/SSE) para progreso en tiempo real.

| Recurso               | Método | Descripción                |
|-----------------------|--------|----------------------------|
| `/jobs`               | GET    | Lista todos los jobs       |
| `/jobs?state=running` | GET    | Filtro por estado          |
| `/jobs/{id}`          | GET    | Estado/progreso/resultado  |
| `/jobs/{id}/cancel`   | POST   | Cancela un job en curso    |

```json
GET /api/v1/jobs/job_123
→ {
  "job_id": "job_123",
  "type": "resolve",
  "state": "completed",
  "progress": 100,
  "started_at": "...",
  "finished_at": "...",
  "result": { "score_id": "19eeb77f2caa", "provider": "openscore" }
}
```

## Cache

```json
GET /api/v1/cache               → { "entries": 42, "total_size_mb": 128 }
DELETE /api/v1/cache             → limpia toda la caché
DELETE /api/v1/cache/abc123      → invalida una entrada
```

## Libraries

Múltiples bibliotecas con configuración independiente (coro, personal, trabajo,
pruebas, temporal).

| Recurso               | Método      | Descripción                   |
|-----------------------|-------------|-------------------------------|
| `/libraries`          | GET         | Lista bibliotecas             |
| `/libraries`          | POST        | Crea una biblioteca           |
| `/libraries/{id}`     | GET, DELETE | Detalle / elimina             |
| `/libraries/{id}/scores` | GET      | Scores de esa biblioteca      |

```json
GET /api/v1/libraries
→ { "libraries": [ { "id": "coral", "name": "Coro", "path": "...", "scores": 42 }, ... ] }
```

## Import / Export

```json
POST /api/v1/import
{ "source": "file.mxl", "library": "coral" }
→ { "score_id": "sc_imported_1" }

POST /api/v1/export
{ "score_id": "sc1", "format": "pdf" }
→ 202 { "job_id": "job_export_1", "type": "export", "state": "running" }
```

## Configuración por módulos

No un único `/settings`, sino desglosado por subsistema:

| Recurso                    | Método  | Descripción              |
|----------------------------|---------|--------------------------|
| `/settings/providers`      | GET, PUT| Proveedores habilitados, orden, tokens |
| `/settings/pipeline`       | GET, PUT| Etapas, orden, parámetros |
| `/settings/users`          | GET, PUT| Perfiles de usuario      |
| `/settings/datasets`       | GET, PUT| cache_dir, streaming, num_proc, download_mode |
| `/settings/cache`          | GET, PUT| TTL, tamaño máximo, versión |

## Administración

| Recurso                      | Método | Descripción                        |
|------------------------------|--------|------------------------------------|
| `/admin/reindex`             | POST   | Reindexa datasets                  |
| `/admin/verify`              | POST   | Verifica integridad de datasets    |
| `/admin/rebuild-knowledge`   | POST   | Reconstruye la base de conocimiento|
| `/admin/compact-cache`       | POST   | Compacta la caché                  |
| `/admin/health-check`        | GET    | Chequeo exhaustivo de salud        |

## Proveedores

| Recurso              | Método(s)        | Descripción                                     |
|----------------------|------------------|-------------------------------------------------|
| `/providers`         | GET              | Lista catálogos y capacidades                   |
| `/providers/{id}`    | GET              | Detalle (formatos, licencia, offline/conexión)   |

## Datasets

| Recurso                       | Método(s) | Descripción                                     |
|-------------------------------|-----------|-------------------------------------------------|
| `/datasets`                   | GET       | Lista datasets registrados                      |
| `/datasets/{id}`              | GET       | Info (tamaño, licencia, formatos, url, estado)   |
| `/datasets/{id}/install`      | POST      | Instala (crea un Job con progreso)               |
| `/datasets/{id}/update`       | POST      | Actualiza                                       |
| `/datasets/{id}/verify`       | POST      | Verifica integridad                              |
| `/datasets/{id}/remove`       | DELETE    | Elimina                                         |
| `/datasets/{id}/location`     | GET       | Ruta en disco                                   |

## Eventos (WebSocket / SSE)

`/events` emite eventos del `EventBus` en tiempo real:

`JobSubmitted`, `JobStarted`, `JobCompleted`, `JobFailed`, `JobCancelled`,
`StageStarted`, `StageFinished`, `StageFailed`, `ProviderStarted`,
`ProviderFinished`, `ProviderFailed`, `DatasetInstalled`, `DatasetUpdated`,
`DatasetRemoved`, `ScoreValidated`, `ScoreMerged`, `LibraryStored`.

## Workspaces (visión de futuro)

Un `Workspace` es un contexto aislado donde un usuario importa documentos,
lanza resoluciones, revisa candidatos, hace correcciones y genera un Score
validado sin afectar a otros proyectos.

```
Workspace
 ├── MusicalDocument
 ├── Jobs
 ├── CandidateRepresentations
 ├── Selected Score
 ├── Correcciones humanas
 ├── Historial
 └── Exportaciones
```

Recursos previstos:

| Recurso                              | Método(s) | Descripción                            |
|--------------------------------------|-----------|----------------------------------------|
| `/workspaces`                        | GET, POST | Lista / crea workspace                 |
| `/workspaces/{id}`                   | GET, DELETE | Detalle / elimina                    |
| `/workspaces/{id}/documents`         | GET, POST | Documentos del workspace               |
| `/workspaces/{id}/jobs`              | GET       | Jobs asociados al workspace            |
| `/workspaces/{id}/scores`            | GET       | Scores del workspace                   |

Un director de coro podría crear un workspace por concierto o repertorio,
trabajar con varias versiones de una obra y decidir cuál adoptar antes de
incorporarla a su biblioteca definitiva.

## Principios

- El backend solo mapea los objetos del **dominio**; nunca filtra a infraestructura.
- Toda operación costosa devuelve un `Job` (`202`) con `job_id`.
- Progreso y notificaciones por `/events` (WebSocket/SSE).
- `ResolveResult`, `QualityReport`, `Job`, `Event` y `UserProfile` son los
  contratos de respuesta principales.
- Cada nivel de identidad se expone como recurso independiente.
- Configuración desglosada por módulo, no monolítica.
- `Merge`, `DuplicateResolver`, `QualityReport` y `KnowledgeBase` son recursos
  de primera clase, no utilidades internas ocultas.
- Observabilidad completa: `health`, `monitor`, `statistics`, `logs`, `pipeline`.
