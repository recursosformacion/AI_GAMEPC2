# Base de datos de osap-api — esquema y descripción de tablas

> Documento de referencia del esquema MySQL de la base de datos **`osap-api`** (el servicio
> de esta carpeta). Describe cada tabla y cada columna, apoyándose en el código que las
> crea/usurca (`src/osap/infrastructure/state/*`) y en la documentación del repositorio.
> Datos de ejemplo y conteos: **snapshot local tomado el 2026-09-06** (pueden variar).

## 1. Conexión

- La conexión está en `osap.toml` (sección `[db]`), con override por variables de entorno
  `OSAP_API_DB_*`. En este entorno de desarrollo apunta a MySQL local:
  - host `127.0.0.1`, base de datos `osap-api`, usuario `osap2027`.
- Motor: **MySQL / InnoDB**, charset `utf8mb4` (collations mixtas
  `utf8mb4_general_ci` / `utf8mb4_unicode_ci` según la tabla).
- El esquema **no se gestiona con migraciones SQL externas**: lo crea cada proceso al
  arrancar con `CREATE TABLE IF NOT EXISTS ...` idempotentes (vía
  `OpStore._init()` y `ResolutionStore._init()`) y lo evoluciona con `ALTER TABLE`
  condicionales en `_migrate()`. Si MySQL no está disponible, el servicio degrada a un
  almacén en memoria (misma interfaz), por lo que estas tablas pueden estar vacías o no
  existir en entornos sin BD.

**Frontera de datos (docs/osap-api-db-decision-v1.md):** la BD de osap-api aloja **solo
estado operativo del propio servicio** (proveedores, config, sugerencias, resoluciones,
índice local de búsqueda). **No** contiene el catálogo autoritativo (obras/compositores/
votos de osap-storage) ni identidad de usuarios (osap-auth).

## 2. Visión general

| # | Tabla | Filas* | Propósito |
|---|-------|-------:|-----------|
| 1 | `app_config` | 7 | Configuración operativa persistente (clave-valor) |
| 2 | `sync_state` | 1 | Marcadores de progreso de las sincronizaciones (índice local) |
| 3 | `providers` | 14 | Registro de proveedores de catálogo (declarativos `yaml` y añadidos en runtime) |
| 4 | `source_suggestions` | 0 | Sugerencias de nuevas fuentes/proveedores hechas por usuarios (auditoría) |
| 5 | `index_works` | 354.703 | Índice local: una fila por **obra única** (deduplicada) para búsqueda rápida |
| 6 | `index_representations` | 445.321 | Índice local: una fila por **representación** (fuente/fichero) de cada obra |
| 7 | `resolution_sessions` | 56 | Una operación concreta de resolución de obra (ADR-0033) |
| 8 | `provider_results` | 116 | Páginas/resultados adquiridos de proveedores durante una sesión |
| 9 | `resolution_items` | 104 | Resultados (obras candidatas) derivados de una sesión, por obra de entrada |
| 10 | `work_selections` | 3 | Representación elegida/validada persistida por obra |
| 11 | `correction_requests` | 2 | Solicitudes de corrección de catálogo / contacto (admin responde) |
| 12 | `authority_entity` | 260 | Fichero auxiliar de autoridad: entidades (obras/compositores) canónicas |
| 13 | `authority_identifier` | 61 | Fichero auxiliar de autoridad: identificadores externos de las entidades |

\* Conteo de filas aproximado (`information_schema` no es exacto para InnoDB) del entorno local.

### Agrupación funcional

- **Configuración operativa**: `app_config`, `sync_state`.
- **Proveedores / fuentes**: `providers`, `source_suggestions`.
- **Índice local de búsqueda**: `index_works`, `index_representations`.
- **Motor de resolución**: `resolution_sessions`, `provider_results`, `resolution_items`
  (+ selección persistida en `work_selections`).
- **Feedback / administración**: `correction_requests`.
- **Autoridad auxiliar** (tablas locales, no creadas por el código de esta app): `authority_entity`, `authority_identifier`.

### Relaciones lógicas

```
providers ──────────────────────────────────────────┐
source_suggestions                                  │ (registro + wiring en arranque)
                                                    ▼
resolution_sessions 1 ──── n provider_results       │  provider_results.session_id
       │ 1 ──── n resolution_items                  │  resolution_items.session_id
       │ (selección final -> selection_json)        │
work_selections (por work_id, cache de selección)   │
                                                    │
index_works 1 ──── n index_representations          │  index_representations.work_id -> index_works.id
authority_entity 1 ──── n authority_identifier      │  authority_identifier.entity_key -> authority_entity.entity_key
```

No existen claves foráneas físicas (FK): las relaciones son lógicas por convención de
columnas (`*_id`, `session_id`, `work_id`, `entity_key`).

### Convenciones transversales

- **Marcas de tiempo**: columnas `*_at` son `VARCHAR(64)` con fecha **ISO 8601 en UTC**
  (p. ej. `2026-08-15T10:25:31.244869+00:00`); algunos scripts usan `NOW()` de MySQL
  (`YYYY-MM-DD HH:MM:SS`). No son tipos `DATETIME`/`TIMESTAMP`.
- **JSON**: las columnas `*_json`, `payload_json`, `mapping`, `config`, etc. guardan JSON
  serializado como texto; se codifican con `json.dumps(..., ensure_ascii=False)` y se
  decodifican al leer. No se usa tipo `JSON` de MySQL.
- **Booleans**: `TINYINT` con `1/0` (columna `wired`, `available`).
- **IDs**: generados por la app (prefijos como `sug-`, `corr-`) o UUIDs; el índice usa
  `BIGINT UNSIGNED AUTO_INCREMENT`.

---

## 3. `app_config` — configuración operativa

Configuración persistente en la BD que el servicio lee al arrancar y consulta en runtime
con precedencia **variable de entorno > osap.toml > BD (`app_config`) > defaults en código**
(`src/osap/bootstrap/configuration.py::load_configuration`). Las claves corresponden a
campos de la dataclass `Configuration`.

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `key` | `VARCHAR(128)` | PK | Nombre del campo de configuración (p. ej. `service_client_id`, `deployment`, `default_output_format`, `admin_client_secret`). |
| `value` | `TEXT` | — | Valor del campo, en texto (se convierte al tipo del campo al cargar: int/bool/float/str). |
| `updated_at` | `VARCHAR(64)` | — | Última actualización (ISO 8601 UTC). |

- Escritura: `OpStore.set_config(key, value)` (upsert). Lectura: `OpStore.get_config(key)`.
- Filas vistas en local: credenciales de servicio/admin (`service_client_id`/`_secret`,
  `admin_client_id`/`_secret`), `deployment=dev`, `dev_mode=0`, `default_output_format=musicxml`.
  **Cuidado**: contiene secretos (client secrets) en claro.

## 4. `sync_state` — estado de sincronizaciones

Marcadores persistidos por los procesos de sincronización del índice local, para que cada
pasada **reanude donde terminó la anterior** sin rehacer trabajo (idempotencia).

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `key` | `VARCHAR(64)` | PK | Clave del marcador. Convención por proveedor: `index.imslp.start`, `index.omr.last_work_id`, `index.mutopia.start_at` (ver `script/sync_index.py::_KEYS`). |
| `value` | `VARCHAR(255)` | — | Valor del marcador (p. ej. último `start` de IMSLP o último `work_id` de OMR procesado). |
| `updated_at` | `VARCHAR(64)` | — | Última actualización. |

- Escritura: `OpStore.set/get_sync_state` y `script/sync_index.py`. La fila local
  (`test.sync.probe`) es una prueba; en producción guarda los marcadores del índice.

## 5. `providers` — registro de proveedores de catálogo

Una fila por proveedor de catálogo. En desarrollo los proveedores se registran por su
definición declarativa YAML (`providers/{omr,imslp,...}/provider.yaml`), y las columnas
`endpoints`, `mapping`, `resources`, `transforms` materializan los ficheros YAML del
proveedor serializados a JSON. También permite **añadir/activar proveedores dinámicos**
en runtime vía API de administración.

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `provider_id` | `VARCHAR(128)` | PK | Identificador corto del proveedor (`imslp`, `omr`, `mutopia`, `musicbrainz`, `openscore`, `cpdl`, `kernscores`, …). Se usa en `IndexCatalogProvider`, resolución, etc. |
| `name` | `VARCHAR(255)` | — | Nombre legible del proveedor. |
| `kind` | `VARCHAR(32)` | — | Tipo de registro: `yaml` (definición declarativa en `providers/*`) o `dynamic` (añadido por API/admin). Default `'dynamic'`. |
| `base_url` | `VARCHAR(1024)` | — | URL base del servicio/fetcher del proveedor (nullable). |
| `wired` | `TINYINT` | — | `1` si el proveedor está **activo** (registrado como proveedor del catálogo al arrancar); `0` si solo está definido/conocido. |
| `config` | `TEXT` | — | JSON con la configuración del conector (se guarda `json.dumps(config)`; al leer se decodifica a dict). |
| `created_at` | `VARCHAR(64)` | — | Fecha de alta (ISO 8601 UTC). |
| `description` | `TEXT` | — | Descripción **multi-idioma en JSON** (p. ej. `{"en": "..."}`); acepta también texto plano (se envuelve como `{"en": ...}`). |
| `endpoints` | `TEXT` | — | JSON con la sección `endpoints` del proveedor (endpoints de API consultados por el fetcher). |
| `mapping` | `TEXT` | — | JSON con el `mapping` (normalización de respuestas del proveedor al contrato `ProviderWork`). |
| `resources` | `TEXT` | — | JSON con la sección `resources` (catálogo de recursos del proveedor, `resources.yaml`). |
| `transforms` | `TEXT` | — | JSON con la sección `transforms` (transformaciones aplicadas a los datos del proveedor). |

- Escritura: `OpStore.upsert_provider` (usado por seeds como `reseed_providers.py`,
  `seed_missing_providers.py` y por la API admin para proveedores dinámicos),
  `OpStore.delete_provider`, `OpStore.set_provider_wired`.
- Lectura en arranque: `wiring.py::_provider_definition`, `_db_provider_metadata`
  (decide qué proveedores se conectan y qué YAML se cargan). Al devolver filas se
  decodifica JSON (`_decode_provider_row`).
- Filas vistas: 14 (11 `yaml` + 3 `dynamic`); activos (`wired=1`): `cpdl`, `imslp`,
  `musicbrainz`, `mutopia`, `omr`, `openscore`, `rism`.

## 6. `source_suggestions` — sugerencias de fuentes

Permite que un usuario con sesión sugiera una nueva fuente/proveedor de partituras. El
admin la aprueba o cancela; el flujo **no modifica el catálogo** (solo registra la
petición y su auditoría). API: `POST/GET .../sources/suggestions` en `platform.py`.

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `id` | `VARCHAR(64)` | PK | ID de la sugerencia (generado como `sug-<n>`). |
| `name` | `VARCHAR(255)` | — | Nombre de la fuente sugerida. |
| `type` | `VARCHAR(64)` | — | Tipo de fuente, texto libre enviado por el usuario (p. ej. catálogo/OMR/autoridad). |
| `location` | `VARCHAR(1024)` | — | Localización/URL de la fuente sugerida. |
| `mapping` | `TEXT` | — | JSON propuesto de mapeo de la fuente (cómo se normalizarían sus datos). |
| `requested_by` | `VARCHAR(255)` | — | `user_id` del usuario que la propuso. |
| `status` | `VARCHAR(32)` | — | Estado: `pending` / `approved` / `cancelled` (default `'pending'`). |
| `admin_message` | `TEXT` | — | Mensaje del admin al resolver (nullable). |
| `created_at` | `VARCHAR(64)` | — | Fecha de creación (ISO 8601 UTC). |
| `decided_at` | `VARCHAR(64)` | — | Fecha de la decisión (nullable). |
| `decided_by` | `VARCHAR(255)` | — | `user_id` del admin que resolvió (nullable). |

## 7. `index_works` — índice local de obras (búsqueda)

Índice local derivado para búsqueda rápida/determinista (ver
`docs/osap/search-index-evolution.md`). Una fila por **obra única**: los indexadores
(`script/index_works.py`, `script/sync_index.py`) normalizan y deduplican por
`title_key + composer_id`. El proveedor `IndexCatalogProvider` (`.../catalogs/index/`)
hace `SELECT` sobre esta tabla + `index_representations` en ~ms. Es un **derivado**, no
una copia del catálogo de storage; se construye en prod por un job/sync.

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK (auto) | ID interno de la obra en el índice. |
| `title` | `VARCHAR(1024)` | — | Título tal como se muestra (según el proveedor/canonicalizador). En FULLTEXT junto a `composer_name`. |
| `title_key` | `VARCHAR(255)` | Índice | **Título normalizado** (minúsculas, sin signos, sin artículo inicial, … por `MetadataNormalizer`) → clave de deduplicación y de búsqueda por prefijo/LIKE. |
| `composer_name` | `VARCHAR(255)` | — | Nombre canónico del compositor (para mostrar y buscar); puede ser `'NA'` si no se conoce. En FULLTEXT. |
| `composer_id` | `VARCHAR(36)` | Índice | UUID del compositor en el **Maestro** (osap-storage), si está identificado; `NULL` si es anónimo/desconocido. |
| `catalogue` | `VARCHAR(255)` | — | Número de catálogo tal como llega (p. ej. `K. 525`). |
| `catalogue_key` | `VARCHAR(128)` | Índice | Catálogo **normalizado** (p. ej. `k525`) para buscar queries que son catálogos sin falsos positivos. |
| `year` | `SMALLINT` | — | Año de composición (nullable). |
| `instrumentation` | `VARCHAR(255)` | — | Instrumentación/plantilla textual. |
| `genre_id` | `INT UNSIGNED` | — | ID de género copiado de `osap-storage.works.genre_id` (denormalizado del corpus OMR); se usa para filtrar por `genre_id IN (...)`. |
| `source_count` | `TINYINT` | — | Nº de **proveedores distintos** que aportan representaciones a la obra (se recalcula al final de cada pasada de indexado: `COUNT(DISTINCT provider)` de `index_representations`). |
| `updated_at` | `VARCHAR(64)` | — | Última actualización de la fila. |

- Unicidad: `(title_key(191), composer_id)` → el dedupe es `INSERT ... ON DUPLICATE KEY
  UPDATE` (actualiza metadatos en vez de duplicar).
- Índices: `idx_idx_title(title_key)`, `idx_idx_composer(composer_id)`,
  `idx_idx_catalogue(catalogue_key)` y FULLTEXT `ft_idx_title_composer(title,
  composer_name)` (búsqueda de un token con `MATCH ... IN BOOLEAN MODE 'moz*'`).

## 8. `index_representations` — representaciones del índice

Una fila por cada **representación/fichero** de una obra del índice (una obra puede tener
varias: varios proveedores, formatos o títulos de proveedor distintos).

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `id` | `BIGINT UNSIGNED` | PK (auto) | ID interno de la representación. |
| `work_id` | `BIGINT UNSIGNED` | Índice | FK lógica → `index_works.id`. |
| `provider` | `VARCHAR(64)` | — | Proveedor de la representación (`omr`, `imslp`, `mutopia`, `musicbrainz`). |
| `format` | `VARCHAR(32)` | — | Formato: `musicxml`, `pdf`, `midi`, `json`, … |
| `download_url` | `TEXT` | — | URL de descarga/permallink. Para OMR/Mutopia es fichero descargable (redirect); para IMSLP/MusicBrainz es la página del registro (`view_url`, sin fichero). |
| `title_provider` | `VARCHAR(1024)` | — | Título tal como lo dio el proveedor (entra en la unicidad para no duplicar representaciones del mismo proveedor). |
| `available` | `TINYINT` | — | `1` si hay fichero descargable real (OMR MusicXML, Mutopia PDF/MIDI); `0` si solo hay metadata/página (IMSLP PDF sin fichero, MusicBrainz JSON). Se expone al cliente como `metadata.available`. |
| `quality` | `TINYINT` | — | Puntuación/calidad de la representación (default `0` = sin evaluar). |

- Unicidad: `(work_id, provider, format, title_provider(255))` → el indexado de la misma
  página no duplica representaciones.
- Consulta típica de búsqueda (índice): `SELECT ... FROM index_representations r JOIN
  index_works i ON i.id = r.work_id WHERE <filtros> AND r.provider IN (...) ...`.

## 9. `resolution_sessions` — sesiones de resolución

Una sesión representa **una operación concreta de resolución** de una obra (petición del
usuario a `/works/resolve`, ADR-0033 y `docs/osap/resolution-store-v1.md`). La web recibe
`202 + session_id` y consulta estado/resultados mientras un worker adquiere y resuelve en
segundo plano.

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `session_id` | `VARCHAR(64)` | PK | ID de la sesión (devuelto al crear). |
| `status` | `VARCHAR(32)` | Índice | Estado de la sesión: `acquiring` / `resolving` / `complete` / `partial` / `failed` / `expired` (default `'acquiring'`). `partial` = se alcanzaron límites o quedan errores recuperables; `complete` = todos los proveedores del plan llegaron a fin. |
| `query_json` | `TEXT` | — | Consulta original (compositor/título/catálogo/texto libre) en JSON. |
| `providers_json` | `TEXT` | — | Plan de adquisición: proveedores implicados + perfiles/cotas (JSON). |
| `policy_json` | `TEXT` | — | Instantánea de la política/límites aplicados (`max_results_to_acquire`, `max_pages_per_provider`, `max_duration`…) en JSON. |
| `progress_json` | `TEXT` | — | Contadores de progreso (páginas adquiridas, obras adquiridas, ítems resueltos) en JSON. |
| `error` | `TEXT` | — | Mensaje de error si la sesión terminó en `failed` (nullable). |
| `selection_json` | `TEXT` | — | Representación **seleccionada** (resultado normal, no error) persistida al terminar; la consume el endpoint de `score_contract`. (Columna añadida por migración.) |
| `created_at` | `VARCHAR(64)` | — | Creación (ISO 8601 UTC). |
| `updated_at` | `VARCHAR(64)` | Índice | Última actualización (se refresca con `touch()`; usado para detectar sesiones colgadas). |
| `expires_at` | `VARCHAR(64)` | — | TTL de la sesión; al expirar se borran `provider_results` y `resolution_items` (la fila de sesión se conserva y pasa a `expired`). |

## 10. `provider_results` — páginas adquiridas en una sesión

Registro exacto de lo adquirido a cada proveedor **durante una operación**. Permite no
volver a descargar una página, reanudar tras un corte (`next_cursor`) y **re-ejecutar el
matching sin volver a consultar al proveedor** (el `payload` normalizado es suficiente).

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `id` | `VARCHAR(64)` | PK | ID de la fila. |
| `session_id` | `VARCHAR(64)` | Índice | FK lógica → `resolution_sessions.session_id`. |
| `provider` | `VARCHAR(64)` | — | Proveedor de la página (`omr`, `imslp`, `musicbrainz`, `mutopia`, …). |
| `pagination_kind` | `VARCHAR(16)` | — | Mecanismo de paginación del proveedor (p. ej. `start`, `offset`, `cursor`, `page`…). |
| `cursor_value` | `VARCHAR(512)` | — | Token de paginación del proveedor (opaco, no se asume formato). Con `session_id`+`provider` forma la unicidad de página. |
| `next_cursor` | `VARCHAR(512)` | — | Cursor de la siguiente página (para reanudar); `NULL` si el proveedor indicó fin. |
| `status` | `VARCHAR(32)` | — | `fetched` (éxito, payload disponible) / `recoverable_error` (timeout/5xx, reintentable) / `end_of_provider` (no hay más páginas). Default `'fetched'`. |
| `payload_json` | `MEDIUMTEXT` | — | JSON con la lista de `ProviderWork` **normalizados** de la página (suficiente para reconstruir el universo y re-resolver). |
| `meta_json` | `TEXT` | — | Metadatos del transporte (estado HTTP, etag, etc.) en JSON. |
| `acquired_at` | `VARCHAR(64)` | — | Cuándo se obtuvo la página. |

- Unicidad: `(session_id, provider, cursor_value)` → la inserción es idempotente; una
  página no se adquiere dos veces en la misma sesión.

## 11. `resolution_items` — resultados derivados de una sesión

Una fila por **obra de entrada** de la sesión con su resultado de matching. Los
candidatos van **embebidos** (JSON por ítem); nunca hay tabla global de obras.

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `id` | `VARCHAR(64)` | PK | ID del ítem. |
| `session_id` | `VARCHAR(64)` | Índice | FK lógica → `resolution_sessions.session_id`. |
| `ref_json` | `TEXT` | — | La obra de entrada (compositor, título, catálogo, `source_provider`, `source_work_id`) en JSON. |
| `status` | `VARCHAR(32)` | Índice | Estado **de esa obra**: `resolved` / `ambiguous` / `not_found`. |
| `resolution_stage` | `VARCHAR(16)` | — | `provisional` (matching con universo parcial) o `definitive` (universo completo). Default `'provisional'`. |
| `revision` | `INT` | — | Nº de versión del resultado: `1` provisional, `2` provisional mejorado, `3` definitivo. Solo sube cuando el contenido cambia (idempotencia). |
| `normalized_json` | `TEXT` | — | Formas comparables (`title_raw`, `title`, `composer_raw`, `composer`, `catalog`) en JSON. |
| `resolved_json` | `TEXT` | — | Conclusión: `work` y `composer` resueltos (nullable si sin resolver). |
| `confidence` | `DECIMAL(6,5)` | — | Confianza de la resolución (0.00000–1.00000). |
| `candidates_json` | `TEXT` | — | Candidatos embebidos en JSON (no tabla global). |
| `evidence_json` | `TEXT` | — | Evidencias por proveedor en JSON. |
| `updated_at` | `VARCHAR(64)` | — | Última actualización (permite reconstruir el momento). |

- Escritura por reemplazo de conjunto (`ResolutionStore.replace_items`): upserta los ítems
  de la sesión y borra los que ya no aplican; `revision` sube solo si cambió el contenido.

## 12. `work_selections` — representación elegida por obra

Cache/estado de la **mejor representación validada** elegida para una obra (resultado de
`BestRepresentationSelector`), para no re-seleccionar cada vez. Se persiste al seleccionar
(API de selección/`score`) y se lee para devolver la selección de una obra.

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `work_id` | `VARCHAR(128)` | PK | ID de la obra (formato heterogéneo: id numérico de OMR, `work-<n>`, etc.). |
| `selection_json` | `TEXT` | — | JSON de la selección: `{provider, format, url, source_id, quality_level, quality_score, reason}`. |
| `updated_at` | `VARCHAR(64)` | — | Última actualización. |

## 13. `correction_requests` — solicitudes de corrección / contacto

Formulario de contacto y de **correcciones al catálogo** (título, compositor, proveedor…)
que quedan `pending` y resuelve el admin (`reviewed`/`closed`). El catálogo **no se
modifica aquí**: solo se registra la petición y su auditoría (kind `contact` es público;
el resto requiere login).

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `id` | `VARCHAR(64)` | PK | ID de la solicitud (generado como `corr-<n>`). |
| `kind` | `VARCHAR(32)` | — | Tipo: `contact` (mensaje general), `composer`, `work`, `source` (corrección de una entidad del catálogo), etc. |
| `entity_id` | `VARCHAR(255)` | — | ID de la entidad a corregir (composer/work id, `provider_id` si `kind=source`…). Nullable (p. ej. contacto). |
| `entity_provider` | `VARCHAR(128)` | — | Proveedor de la entidad (si aplica). Nullable. |
| `field` | `VARCHAR(128)` | — | Campo concreto a corregir (p. ej. `name`, `title`, `description`). Nullable. |
| `current_value` | `VARCHAR(1024)` | — | Valor actual del campo (nullable). |
| `proposed_value` | `VARCHAR(1024)` | — | Valor propuesto por el usuario (nullable). |
| `message` | `TEXT` | — | Mensaje/explicación del solicitante (obligatorio). |
| `contact_email` | `VARCHAR(255)` | — | Email de contacto (para `kind=contact`). |
| `requested_by` | `VARCHAR(255)` | — | `user_id` del solicitante (solo si hizo login; `NULL` en contacto). |
| `requested_by_name` | `VARCHAR(255)` | — | Nombre del usuario autenticado (de la sesión OIDC). (Migración.) |
| `requested_by_email` | `VARCHAR(255)` | — | Email del usuario autenticado. (Migración.) |
| `status` | `VARCHAR(32)` | — | `pending` (default) / `reviewed` / `closed` (valores puestos por la API admin). |
| `admin_message` | `TEXT` | — | Mensaje del admin al resolver (nullable). |
| `created_at` | `VARCHAR(64)` | — | Fecha de creación (ISO 8601 UTC). |
| `decided_at` | `VARCHAR(64)` | — | Fecha de la decisión (nullable). |
| `decided_by` | `VARCHAR(255)` | — | `user_id` del admin que resolvió (nullable). |

- Validación previa al guardar: la entidad referenciada debe existir (`source` → entre los
  proveedores conocidos; `composer`/`work` → en osap-storage) para los kinds de corrección.
- Filas vistas: 2 en `pending` (`kind=composer`, `kind=source`).

## 14. `authority_entity` y `authority_identifier` — fichero auxiliar de autoridad

> **Nota de procedencia**: estas dos tablas existen en la BD local pero **no las crea ni
> las lee el código de `src/osap`** (no hay DDL ni SQL en esta app). Aparecen también en el
> dump portátil `_portatil/osap-api.sql` y el script `script/sync_db_down.ps1` las excluye
> expresamente al restaurar («no vienen del VPS»). Son un **fichero de autoridad auxiliar
> cargado localmente** (fuente `open`/`wikidata`, fechas 2026-08-15) sobre un subconjunto
> de obras abiertas y compositores. Se describen aquí por su presencia en el esquema, con
> la semántica que se deduce de columnas y datos.

### `authority_entity` — entidades de autoridad

Entidad canónica (obra o compositor) con su forma de visualización. Datos vistos: 251
`work` (fuente `open`) + 9 `composer` (fuente `wikidata`).

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `entity_key` | `VARCHAR(128)` | PK | Clave de la entidad: slug/título normalizado para obras (p. ej. `ave verum corpus`) o clave de compositor (p. ej. `f schubert`). Es el enlace con `authority_identifier`. |
| `entity_type` | `VARCHAR(16)` | Índice | Tipo de entidad: `work` o `composer`. |
| `canonical` | `VARCHAR(512)` | — | Forma canónica legible de la entidad (título canónico o nombre canónico). |
| `composer_ref` | `VARCHAR(128)` | — | Referencia de compositor asociada a la obra (nombre/atribución tal como viene de la fuente; nullable). En los datos `open` puede incluir anotaciones de arreglo (p. ej. `arr. …`). |
| `source` | `VARCHAR(32)` | — | Procedencia de la fila: `open` (corpus abierto) o `wikidata`. Default `'wikidata'`. |
| `updated_at` | `VARCHAR(64)` | — | Última actualización. |

### `authority_identifier` — identificadores externos de las entidades

Identificadores de autoridad externos asociados a una entidad (para enriquecer/matchear
por IDs estables: Wikidata, VIAF, ISNI, LCCN, MusicBrainz, …).

| Columna | Tipo | Clave | Descripción |
|---|---|---|---|
| `entity_key` | `VARCHAR(128)` | PK (compuesta) | Clave de la entidad (→ `authority_entity.entity_key`). |
| `identifier_kind` | `VARCHAR(32)` | PK (compuesta) | Esquema del identificador: `wikidata`, `viaf`, `isni`, `lccn`, `musicbrainz`, `wikidata_work`… |
| `identifier_value` | `VARCHAR(256)` | Índice | Valor del identificador (p. ej. `Q210211`, `0000000120958492`, `f91e3a88-…`). |
| `source` | `VARCHAR(32)` | — | Procedencia del identificador (`open`/`wikidata`). Default `'wikidata'`. |
| `updated_at` | `VARCHAR(64)` | — | Última actualización. |

- Unicidad: `(entity_key, identifier_kind)` → una entidad puede tener un solo valor por
  esquema. Índice auxiliar `(identifier_kind, identifier_value)` para búsquedas inversas
  (¿qué entidad tiene este ID?).

---

## 5. Referencias

**Código que crea/escribe las tablas**

| Tabla(s) | Origen |
|---|---|
| `app_config`, `providers`, `source_suggestions`, `sync_state`, `index_works`, `index_representations`, `correction_requests`, `work_selections` | `src/osap/infrastructure/state/op_store.py` (`_init` + `_migrate`) |
| `resolution_sessions`, `provider_results`, `resolution_items` | `src/osap/infrastructure/state/resolution_store.py` (`_init`) |
| Índice (build/sync) | `script/index_works.py`, `script/sync_index.py` |
| `authority_entity`, `authority_identifier` | Sin creador en `src/` (local/auxiliar) — ver nota en §14 |

**Consumidores principales**

- `src/osap/api/platform.py` — sugerencias, correcciones, selección de obra,
  `score_contract`, resolución.
- `src/osap/bootstrap/wiring.py` — proveedores desde BD, `IndexCatalogProvider`.
- `src/osap/infrastructure/catalogs/index/index_catalog_provider.py` — búsqueda sobre el índice.
- `src/osap/bootstrap/configuration.py` — overrides de config desde `app_config`.

**Documentación relacionada**

- `docs/osap-api-db-decision-v1.md` — frontera de la BD de osap-api.
- `docs/configuration-v1.md` — `osap.toml` + `app_config`.
- `docs/osap/search-index-evolution.md` — diseño del índice (`index_works`/`index_representations`).
- `docs/osap/resolution-store-v1.md` y `docs/osap/adr/0033-resolution-sessions.md` — modelo de resolución.
- `docs/osap/providers-layer.md` — capa de proveedores y columnas YAML/JSON de `providers`.
