# Diseño — Estadísticas de uso y proveedores (v1)

**Estado:** diseño inicial cerrado y aprobado (2026-09-12). **F-A implementada** (store
memory+MySQL, contracts, `AnalyticsRecorder`, contadores de búsquedas y descargas,
`GET /api/v1/admin/analytics/overview`). F-B→F-D pendientes.
**Alcance:** primera capa de analítica (uso, proveedores, carencias de catálogo).
**No toca:** búsqueda, agrupación (WorkGrouper/work_resolver) ni resolución.
**No es:** `work_statistics` (valoración por votos, vive en osap-storage).

Este documento concreta **qué evento produce cada contador** y **cuál es la granularidad**
de almacenamiento. No se mezcla con el proyecto de nueva BBDD.

---

## 1. Eventos → contadores

| # | Evento | Señal real en el código | Contadores que actualiza | Granularidad |
|---|--------|-------------------------|--------------------------|--------------|
| E1 | Búsqueda completada (una por llamada; **cache hit cuenta igual**) | `SearchMixin.create_search` → `_run()` con `total` final (`api/platform/search.py:137-165`) y camino de cache hit (`:83-97`) | `analytics_search_daily.total`, `.with_results`, `.without_results` | día (UTC) |
| E2 | Representación **consultada** (abierta por el usuario) | `GET /api/v1/representations/{id}/download?view=1` (`api/http/search.py:68`), que es lo que usa el visor (`web/src/pages/ViewerPage.tsx:206`, `WorkDetailTabs.tsx:446`) | `analytics_consults_daily(provider, format, work_id)`, `analytics_provider_daily.consults` | día + proveedor + obra |
| E3 | **Descarga** | `GET /api/v1/representations/{id}/download` sin `view` (`api/http/search.py:68`; `view=0`) y `GET /api/v1/omr/download` (`api/http/omr.py:33`) | `analytics_downloads(day,user,provider,work_id,format,quantity,bytes)`, `analytics_provider_daily.downloads`, `.bytes` | **día + usuario + proveedor** |
| E4 | Descarga/adquisición fallida | mismo hook: `upstream != 200` o `requests.RequestException` (`api/http/search.py:91-94`); resolución: `AcquiredPage.error` (`infrastructure/resolution/provider_acquirer.py:35,102`) | `analytics_provider_daily.downloads_failed` / `.osap_failed` | día + proveedor |
| E5 | Adquisición de OSAP (trae el fichero a storage/índice) | worker de resolución / `provider_acquirer.acquire_page` (éxito) | `analytics_provider_daily.osap_acquired` | día + proveedor |
| E6 | Representaciones utilizables / no utilizables | **snapshot diario** de `index_representations` (`available`, `quality`) agrupado por `provider` (`infrastructure/state/op/mysql.py:117-131`) | `analytics_provider_daily.usable`, `.unusable` | día + proveedor (estado, no evento) |
| E7 | Obras consultadas / más consultadas | derivado de E2 agrupando por `work_id` | `analytics_work_consults_daily` | día + obra |
| E8 | Obras con/sin representación utilizable (huecos) | snapshot diario: `index_works LEFT JOIN index_representations` | `analytics_catalogue_daily.works_with_usable`, `.works_without_usable` | día (snapshot) |

**Distinción clave (evita inflar):** “consultada” = E2 (`?view=1`, el usuario abre el fichero en
el visor). Que una representación **aparezca en resultados** no cuenta como consulta.

### Semántica cerrada (aprobada 2026-09-12)

- **`downloads` = solicitudes de descarga iniciadas desde OSAP**, no garantía de descarga física
  completada. En storage propio (`omr`/`mutopia`) OSAP sirve el fichero y mide `bytes`; en
  proveedores externos OSAP entrega la URL (302) y **no** puede confirmar que el usuario
  complete la descarga en el proveedor. Se cuenta la solicitud, con `bytes = 0` en ese caso.
- **Una búsqueda cuenta exactamente una vez por llamada a `POST /api/v1/searches`**, con
  independencia del camino interno: el **cache hit cuenta igual** que la búsqueda ejecutada
  (`cache hit` y `_run()` son caminos de la misma llamada; nunca se cuenta dos veces la misma
  llamada, ni se deja de contar por servirse de caché).


**Proveedor y obra en los eventos de descarga/consulta:** el id es determinista
`idx-<work_id>-<provider>-<format>` (`index_catalog_provider.py:179-227`), así que ambos se
derivan del `representation_id` sin tocar la lógica. `get_representation` hoy **no** devuelve
`provider`/`work_id` en el dict (`index_catalog_provider.py:220-227`): se añaden dos claves al
dict (cambio aditivo) o se parsea el id en el hook de analítica. Recomendado: añadirlas al dict.

---

## 2. Granularidad y esquema de almacenamiento

Motor: MySQL operativo de osap-api (mismo `op_store_config`, `pymysql`, `CREATE TABLE IF NOT
EXISTS` + migración idempotente; ver `infrastructure/state/op/mysql.py:47,175`). Convenciones:
`VARCHAR` para fechas, `utf8mb4`, `INDEX`/`UNIQUE KEY`, upserts `ON DUPLICATE KEY UPDATE`.

```sql
-- E1: agregado diario de búsquedas (sin usuario, sin query)
CREATE TABLE IF NOT EXISTS analytics_search_daily (
    day CHAR(10) NOT NULL,              -- YYYY-MM-DD (UTC)
    total INT NOT NULL DEFAULT 0,
    with_results INT NOT NULL DEFAULT 0,
    without_results INT NOT NULL DEFAULT 0,
    PRIMARY KEY (day)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- E2/E7: consultas por obra (sin usuario)
CREATE TABLE IF NOT EXISTS analytics_consults_daily (
    day CHAR(10) NOT NULL,
    work_id VARCHAR(64) NOT NULL,
    provider VARCHAR(64) NOT NULL DEFAULT '',   -- '' = agregado de obra
    format VARCHAR(32) NOT NULL DEFAULT '',
    consults INT NOT NULL DEFAULT 0,
    PRIMARY KEY (day, work_id, provider, format)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- E3: descarga = única dimensión con usuario
CREATE TABLE IF NOT EXISTS analytics_downloads (
    day CHAR(10) NOT NULL,
    user_id VARCHAR(64) NOT NULL,       -- UUID opaco de osap-auth; 'anon' si no autenticado
    provider VARCHAR(64) NOT NULL,
    work_id VARCHAR(64) NOT NULL DEFAULT '',
    format VARCHAR(32) NOT NULL DEFAULT '',
    quantity INT NOT NULL DEFAULT 0,
    bytes BIGINT NOT NULL DEFAULT 0,    -- 0 si es redirección externa (sin bytes medibles)
    PRIMARY KEY (day, user_id, provider, work_id, format)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- E2..E6: agregado diario por proveedor (upsert desde eventos + snapshot E6)
CREATE TABLE IF NOT EXISTS analytics_provider_daily (
    day CHAR(10) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    consults INT NOT NULL DEFAULT 0,
    downloads INT NOT NULL DEFAULT 0,
    downloads_failed INT NOT NULL DEFAULT 0,
    osap_acquired INT NOT NULL DEFAULT 0,
    osap_failed INT NOT NULL DEFAULT 0,
    bytes BIGINT NOT NULL DEFAULT 0,
    usable INT NOT NULL DEFAULT 0,
    unusable INT NOT NULL DEFAULT 0,
    PRIMARY KEY (day, provider)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- E8: huecos de catálogo (snapshot)
CREATE TABLE IF NOT EXISTS analytics_catalogue_daily (
    day CHAR(10) NOT NULL,
    works_total INT NOT NULL DEFAULT 0,
    works_with_usable INT NOT NULL DEFAULT 0,
    works_without_usable INT NOT NULL DEFAULT 0,
    PRIMARY KEY (day)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Reglas de granularidad:
- **Día = fecha UTC** (`datetime.now(UTC).date().isoformat()`), igual que `vote_day` en votos.
- Semana/mes → **rollups en lectura** (SUM/GROUP BY); no se almacenan.
- Upserts: `INSERT ... ON DUPLICATE KEY UPDATE x = x + VALUES(x)` (eventos) o `x = VALUES(x)`
  (snapshots E6/E8).
- Retención: agregados indefinidos; `analytics_downloads` se pseudonimiza al borrar usuario.
- `bytes` solo es medible en descargas servidas por OSAP (storage propio: `omr`/`mutopia`).
  En proveedores externos (IMSLP/CPDL…) la ruta responde 302 al navegador
  (`api/http/search.py:115-118`) → `bytes = 0`, pero cuenta como descarga/consulta.

---

## 3. Puntos de enganche (código)

| Punto | Fichero:línea | Qué se registra |
|---|---|---|
| Fin de búsqueda (async e hit de caché) | `api/platform/search.py:137-165` (dentro de `_run`) y `:83-97` (cache hit) | E1 |
| Descarga/consulta HTTP | `api/http/search.py:68-118` | E2 (`view=1`), E3, E4, bytes |
| Proxy OMR | `api/http/omr.py:33-65` | E3/E4 (sin `view`; usado para ficheros de storage) |
| Usuario actual | `ctx.api.current_user(authorization)` (`api/platform/votes_users.py:39`, `Principal.user_id` en `domain/principal.py:46`) | atribución de E3 |
| Fallos de adquisición | `infrastructure/resolution/provider_acquirer.py:35,102` | E4/E5 |
| Snapshot utilizables/huecos | nuevo job diario que lee `index_representations` / `index_works` (`state/op/mysql.py:92-131`) | E6/E8 |

Inserción de la capa (siguiendo el patrón op/resolution):
- `infrastructure/state/analytics/{__init__,memory,mysql,factory}.py` + facade
  `infrastructure/state/analytics_store.py` (espejo de `op_store.py`).
- Estado en `PlatformApiCore` (`api/platform/core.py:48-51`) y construcción en
  `PlatformApi.__init__` (`api/platform/main.py:91-92`) desde `container.op_store_config()`.
- Mixin `api/platform/analytics.py` (registrar en `main.py:50-62`) y router
  `api/http/analytics.py` (registrar en `api/platform_app.py`, junto a `build_votes_router`, :107).
- Contratos `api/contracts/analytics.py` (`_Frozen`, pydantic v2) re-exportados en
  `api/contracts/__init__.py`.

**Registro no bloqueante:** insertar en BD en el camino de la petición añade latencia. Se usa un
`BufferedAnalyticsRecorder` (buffer en memoria + flush por lote/cada N s en hilo daemon) que
**nunca** propaga errores (try/except + log). La analítica no puede tumbar una descarga.

**Propiedad arquitectónica (verificada):** un fallo del recorder o del store **no altera la
respuesta** de una búsqueda ni de una descarga. No es una optimización: la analítica es
observación, nunca camino crítico. Tests en `tests/osap/test_analytics.py`:
`test_mixin_never_propagates_analytics_failure`,
`test_recorder_never_raises_on_store_failure`,
`test_search_response_unaffected_when_analytics_explodes`,
`test_download_response_unaffected_when_analytics_explodes`,
`test_download_failure_response_unaffected_when_analytics_explodes`.

---

## 4. API de consulta (admin)

Bajo `require_admin` (`api/platform/votes_users.py:45`), respuesta `SuccessEnvelope[...]`:

- `GET /api/v1/admin/analytics/overview?from&to` → búsquedas (total/con/sin resultados),
  consultas, descargas, bytes.
- `GET /api/v1/admin/analytics/providers?from&to` → tabla por proveedor (consultas, descargas,
  fallidas, bytes, utilizables/no utilizables).
- `GET /api/v1/admin/analytics/works?from&to&limit` → obras más consultadas.
- `GET /api/v1/admin/analytics/catalogue` → obras con/sin representación utilizable (huecos).

---

## 5. Privacidad

- **No** se guarda query ni historial de búsquedas por usuario (solo E1 agregado).
- E2/E7 sin usuario.
- E3 conserva `user_id` + `provider` + día (requisito explícito), con `user_id` = UUID opaco.
- Borrado de usuario: `anonymize_user(user_id)` → `UPDATE analytics_downloads SET user_id='anon'`
  (mismo patrón que `IVoteStore.anonymize_user`).
- `user_id` de peticiones sin token = `'anon'` (no hay identidad).

---

## 6. Fases de implementación

- **F-A (base útil):** store (memory+MySQL+factory), contracts, `BufferedAnalyticsRecorder`,
  E1 (búsquedas), E3/E4 (descargas con usuario+bytes), endpoint `overview`. Sin tocar nada más.
- **F-B:** E2/E7 (consultas de representación/obra) y `provider_daily.consults`.
- **F-C:** E5 (adquisiciones OSAP), E6/E8 (snapshot utilizables y huecos), endpoints
  `providers`, `works`, `catalogue`.
- **F-D:** retención, `anonymize_user`, rollups y, si procede, export.

Tests: `_MemoryStore` directo (patrón `test_resolution_*`), integración MySQL con el fixture de
`tests/osap/test_op_store.py:8-27`, HTTP con `TestClient` (patrón `test_platform_api.py`), y
test del recorder (no propaga errores, flush por lote).

---

## 7. Decisiones abiertas (a confirmar al implementar)

1. **E2 y `?view=1`:** confirmado que el visor usa `view=1`. Los ficheros servidos por
   `omr.py` (storage) no llevan `view`; se contabilizan como **descarga**, no consulta. ¿Se
   quiere distinguir “abrir en visor” de “descargar” también para OMR? (hoy el visor de OMR
   descarga para renderizar).
2. **E1 en caché (cerrado):** el cache hit cuenta igual que la búsqueda ejecutada: una
   llamada = una búsqueda contada. No se deduplica por usuario/día.
3. **Snapshots E6/E8:** ¿job diario programado o cálculo on-read la primera vez del día?
   Propuesto: job diario (un registro por día) para conservar histórico de carencias.
4. **Retención de `analytics_downloads`:** propuesto 24 meses; el resto agregados indefinidos.
