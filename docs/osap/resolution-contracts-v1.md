# Resolution Contracts v1 — HTTP + esquema SQL

> Siguiente paso del ADR-0033 y de `resolution-store-v1.md` (congelado). Define el
> **contrato HTTP exacto** de los tres endpoints y el **esquema SQL** de las tres tablas
> en `OpStore`. Aquí empieza la conversión de la arquitectura a código.

> **Estado: congelado (v1).** Implementación por fases completada: **FASE 1** (persistencia
> + HTTP sin worker), **FASE 2** (máquina de adquisición), **FASE 3** (universo → matching
> provisional → resultados) y **FASE 4** (matching definitivo + `complete`/`partial` +
> TTL + worker + regresión sobre works250). En curso **FASE 5** (ranking/confianza),
> sin tocar contratos ni arquitectura.

## Nota de implementación — FASE 5 (ranking/confianza, dentro del motor)

Disciplina cumplida: **no se tocó** `works/resolve`, `ResolutionSession`, OpStore ni el
contrato HTTP. Solo `ResolutionUniverse → Ranking → Decision` (`work_ranker.py`).

- **5.1 (medición):** `resolution_regression.py` genera la tabla de señales (`--table`/
  `--tsv`), agrupa los falsos resolved y provee el scaffold de evaluación manual
  (`works250.evaluation.json`). Hallazgo: los **72 falsos resolved = 1 candidato + 1
  proveedor, sin margen**.
- **5.2 (ranking antes de decisión):** `WorkRanker` separa `Candidates → Ranking
  (best/second/margin) → Confidence → Decision`. Expone `best_score`, `second_score`,
  `margin`, `matching_providers`, `candidate_count`.
- **5.3 (confianza basada en evidencia):** la decisión usa señales descubiertas
  (multiplicidad de proveedores, margen, compositor), **no** una fórmula de pesos ciega.
  Política configurable: `min_providers` (2) y `min_margin` (0.0).
- **5.4 (atacar los 72 falsos resolved):** un candidato con un solo proveedor, o margen
  insuficiente, o compositor no resuelto → `ambiguous`.
- **5.5 (regresión automática):** el runner imprime `BASELINE / MANUAL EVALUATION /
  NEW RANKER` con la matriz de transición old→new sobre las 250.

### Resultados (baseline → new ranker)

| Métrica | Baseline | New ranker |
|---|---|---|
| resolved | 76 | **4** (solo ≥2 proveedores + compositor) |
| ambiguous | 100 | **172** |
| not_found | 74 | 74 |

Transición: **72 resolved → ambiguous** (los falsos resolved) y **4 resolved → resolved**
(corroborados). `not_found` estable. El resto de la confianza plana (0.9) impide que el
margen discrimine más; con `matching_providers≥2` como señal principal ya se elimina el
falso positivo dominante. La gradación fina del score queda para la siguiente iteración
con las 250 etiquetadas manualmente.

## Nota de implementación — FASE 4

- **Matching definitivo:** al alcanzar `complete`/`partial` se re-resuelve sobre el
  universo completo con `resolution_stage=definitive` (sin llamar a proveedores).
  `resolution_stage` cambia de `provisional` a `definitive` (forzando revisión), mientras
  la adquisición está en curso se mantiene `provisional`.
- **`complete` vs `partial` estrictos (ADR-0033):** `complete` = todos los proveedores
  previstos en EOF + sin páginas pendientes + sin errores recuperables. `partial` = se
  alcanzó `max_pages`/`max_results`/`max_duration`, o se abandonó un proveedor
  (`max_recoverable_retries` superado). Un error recuperable pendiente → `partial`, nunca
  `complete`. `resolved` de una obra no implica `complete` de la sesión.
- **TTL:** al expirar, la sesión pasa a `expired` (200 en GET) y se **eliminan**
  `provider_results` y `resolution_items` (no queda catálogo permanente). La fila de la
  sesión se conserva para auditoría.
- **Worker:** `AcquisitionService` queda conectado en `PlatformApi`
  (`resolve_session`, `run_resolution_worker`); un runtime de jobs conduce las sesiones
  `acquiring` hasta su terminal. Los acquirers de proveedor se inyectan por wiring.
- **Explicabilidad del candidato:** cada candidato de un `resolution_item` lleva
  `matching_providers`, `title_score`, `catalogue_score`, `composer_score` y
  `final_score`, para diseñar el ranking con datos reales (sin tocar todavía los umbrales).
- **Regresión sobre works250:** `script/resolution_regression.py` mide el baseline
  (`works250.results.json`) y detecta los problemas conocidos. Resultado del dataset
  actual: 76 resolved / 100 ambiguous / 74 not_found; **72 falsos resolved** (conf 0.9 con
  1 proveedor) y **98 ambiguous con empate** (confianza plana 0.9). Esto confirma la
  necesidad de gradar la confianza (FASE 5), no una nueva fórmula ciega.

## Nota de implementación — FASE 2

- La máquina de adquisición (`AcquisitionService`) adquiere una página por paso, la
  persiste idempotentemente por `(session_id, provider, cursor_value)` y actualiza el
  progreso. Es reanudable: retoma desde `next_cursor` persistido, sin depender de la
  memoria del proceso.
- `AcquisitionPlan` fija proveedores, paginación, cursor inicial y aplica
  `max_pages_per_provider`, `max_results_to_acquire` y `max_duration_s`. Los límites
  producen `partial`, no `complete`; solo el `end_of_provider` real de todos los
  proveedores produce `complete`.
- **Hallazgo OMR:** el fetcher actual de OMR (`omr_fetcher.py`) **ignora la paginación** y
  devuelve todas las Works en una sola llamada; el adapter no expone metadatos de
  paginación. Por eso el acquirer de adapter entrega una única página y marca
  `end_of_provider`. La máquina se probó con un acquirer paginado determinista (fake) para
  validar multi-página, idempotencia, reanudación y `complete`/`partial`.
- No hay matching todavía: `GET /results` sigue devolviendo `[]`.

## Nota de implementación — FASE 3

- El universo se reconstruye **solo desde `provider_results.payload`** (`rebuild_universe`),
  sin ninguna llamada HTTP. Se pueden reconstruir todas las veces que se quiera de forma
  determinista.
- `SimpleUniverseMatcher` agrupa por título normalizado (+ compositor) → un
  `resolution_item` por obra distinta, con `resolution_stage=provisional`. Es un matching
  provisional determinista; el estado (`resolved`/`ambiguous`) es un heurístico y la
  decisión de confianza definitiva se deja para FASE 4.
- `resolution_items.revision` solo sube **cuando el contenido cambia** (idempotente): el
  mismo universo → dos ejecuciones → mismo resultado (garantía cubierta por test).
- Los resultados se paginan sobre `resolution_items` (Web pagination), desacoplada de la
  de proveedores.
- Hallazgo corregido: `list_all_provider_results` incluye páginas `fetched` y
  `end_of_provider` (ambas con payload); `recoverable_error` no tiene payload y se omite.

## Convenciones

- Envoltorios de respuesta: `SuccessEnvelope` / `ErrorEnvelope`
  (`src/osap/api/contracts.py:603`), con `request_id`.
- `POST /api/v1/works/resolve` deja de ser bloqueante: responde **`202 Accepted`** y
  crea la `ResolutionSession`.
- `OpStore`: MySQL con fallback a memoria, patrón de `op_store.py` (autocommit,
  `utf8mb4`, `CREATE TABLE IF NOT EXISTS` en `_init()`). Los timestamps se guardan como
  `VARCHAR(64)` con `datetime.now(UTC).isoformat()`, igual que el resto de `op_store.py`.

## Concepto: no es un caché

ResolutionSession es un **almacén temporal de una operación de resolución concreta**, no
un caché. Cada búsqueda (`Mozart` y `Mozart Ave Verum`) crea su propia sesión aunque ambas
consulten OMR; **no compartimos resultados entre sesiones por ahora**. Cada sesión tiene
un **presupuesto propio** de tiempo, páginas y resultados. Un caché compartido, si hace
falta, será una optimización independiente posterior sin contaminar `ResolutionSession` ni
convertir osap-api en catálogo.

## 1. `POST /api/v1/works/resolve` → `202`

Crea una `ResolutionSession` y devuelve `session_id` inmediatamente. El trabajo de
adquisición/resolución ocurre en el worker de `domain/jobs`, nunca dentro de esta petición.

### Request

```jsonc
{
  // Dos modos mutuamente excluyentes:
  "query": "Mozart Ave Verum K.618",          // modo query (búsqueda/adquisición)
  // "works": [ { "id": "w1", "composer": {"name": "..."}, "work": {"title": "...", "catalog": "..."} } ],  // modo batch (lote explícito)

  "providers": ["omr", "imslp", "musicbrainz", "mutopia"],   // opcional; por defecto activos

  // Política configurable de la sesión (ADR-0033): opcional; se aplican los defaults.
  "policy": {
    "max_results_to_acquire": 500,    // por proveedor (ver definición)
    "max_pages_per_provider": 20,
    "max_duration_s": 120,            // límite de ejecución de la adquisición (NO es el TTL)
    "ttl_s": 1800                     // TTL de conservación de la sesión (p. ej. 30 min)
  },

  // Opcional: reanudar/reprocesar una sesión existente en lugar de crear una nueva.
  "resume_session_id": "ses_..."
}
```

### Response `202`

```jsonc
{
  "success": true,
  "request_id": "req_...",
  "data": {
    "session_id": "ses_...",
    "status": "acquiring",
    "created_at": "2026-08-14T15:00:00.000000+00:00",
    "expires_at": "2026-08-14T15:30:00.000000+00:00"   // TTL (30 min), no el max_duration
  }
}
```

## 2. `GET /api/v1/sessions/{session_id}` → `200`

Estado de la sesión + progreso + contadores. Para polling de la Web.

```jsonc
{
  "success": true,
  "request_id": "req_...",
  "data": {
    "session_id": "ses_...",
    "status": "resolving",                // acquiring|resolving|complete|partial|failed|expired
    "query": "Mozart Ave Verum K.618",
    "providers": ["omr", "imslp", "musicbrainz", "mutopia"],
    "policy": { "max_results_to_acquire": 500, "max_pages_per_provider": 20, "max_duration_s": 120, "ttl_s": 1800 },
    "progress": {
      "acquired_pages": 12,
      "acquired_works": 490,              // ProviderWork adquiridos (antes de matching/dedup)
      "items_total": 127,
      "items_resolved": 90,
      "items_ambiguous": 20,
      "items_not_found": 17
    },
    "created_at": "2026-08-14T15:00:00.000000+00:00",
    "updated_at": "2026-08-14T15:01:00.000000+00:00",
    "expires_at": "2026-08-14T15:30:00.000000+00:00",   // TTL de conservación
    "error": null
  }
}
```

**Códigos de estado:**
- `200`: la sesión existe (cualquier estado, **incluido `expired`**).
- `404`: **exclusivamente** `session_id` desconocido (nunca existió) o físicamente
  eliminado por el TTL. Así la Web distingue "nunca existió" de "existió pero caducó".

## 3. `GET /api/v1/sessions/{session_id}/results?page=1&per_page=25` → `200`

Resultados de resolución, **paginación de la Web** (desacoplada de la de proveedores).

```jsonc
{
  "success": true,
  "request_id": "req_...",
  "data": {
    "session_id": "ses_...",
    "status": "resolving",
    "resolution_stage": "provisional",    // provisional | definitive
    "revision": 12,                       // monótono: sube cada vez que cambia un resultado
    "page": 1,
    "per_page": 25,
    "total": 127,
    "results": [
      {
        "id": "itm_...",
        "status": "resolved",             // resolved|ambiguous|not_found
        "resolution_stage": "provisional",
        "revision": 12,
        "normalized": { "title_raw": "...", "title": "...", "composer_raw": "...", "composer": "...", "catalog": "K.618" },
        "resolved": { "work": { "title": "Ave Verum Corpus", "catalog": "K.618" }, "composer": { "name": "Wolfgang Amadeus Mozart" } },
        "confidence": 0.94,
        "input_quality": "normal",
        "candidates": [],
        "evidence": [ { "provider": "imslp", "kind": "work_match", "confidence": 0.95 } ]
      }
    ]
  }
}
```

- `resolution_stage` en la raíz de `data` indica si son resultados provisionales o
  definitivos; la Web lo usa para etiquetar "adquiriendo…" frente a "definitivo".
- `404` si `session_id` es desconocido (misma regla que en GET session).

### Semántica de `revision` y `resolution_stage`

- **`revision` es monótono y no tiene una semántica rígida 1/2/3**: **sube cada vez que
  cambia el resultado de un `resolution_item`** (nueva página, más adquisición, matching
  definitivo). Puede haber 1, 4 o N revisiones.
- **`resolution_stage`** (independiente del número de revisiones): `provisional` |
  `definitive`. No atamos el modelo a un número fijo de pasadas.

---

## Esquema SQL (OpStore)

Sigue el patrón existente de `op_store.py` (`_init()` ejecuta `CREATE TABLE IF NOT EXISTS`).
Nota: `cursor` es palabra reservada en MySQL 8 → se usa la columna `cursor_value`.

```sql
CREATE TABLE IF NOT EXISTS resolution_sessions (
    session_id      VARCHAR(64)  PRIMARY KEY,
    status          VARCHAR(32)  NOT NULL DEFAULT 'acquiring',
    query_json      TEXT         NOT NULL,
    providers_json  TEXT         NOT NULL,
    policy_json     TEXT         NOT NULL,      -- incluye max_duration_s (ejecución) y ttl_s (conservación)
    progress_json   TEXT         NOT NULL,
    error           TEXT,
    created_at      VARCHAR(64)  NOT NULL,
    updated_at      VARCHAR(64)  NOT NULL,
    expires_at      VARCHAR(64)  NOT NULL,      -- TTL de conservación (NO el max_duration de ejecución)
    INDEX idx_rs_status  (status),
    INDEX idx_rs_updated (updated_at)
);

CREATE TABLE IF NOT EXISTS provider_results (
    id              VARCHAR(64)  PRIMARY KEY,
    session_id      VARCHAR(64)  NOT NULL,
    provider        VARCHAR(64)  NOT NULL,
    pagination_kind VARCHAR(16)  NOT NULL,      -- page | cursor
    cursor_value    VARCHAR(512) NOT NULL,      -- token de paginación del proveedor (opaco)
    next_cursor     VARCHAR(512),               -- NULL si EOF
    status          VARCHAR(32)  NOT NULL DEFAULT 'fetched',  -- fetched | recoverable_error | end_of_provider
    payload_json    MEDIUMTEXT,                 -- lista de ProviderWork normalizados
    meta_json       TEXT,
    acquired_at     VARCHAR(64)  NOT NULL,
    UNIQUE KEY uq_pr_cursor (session_id, provider, cursor_value),  -- idempotencia: una página una vez
    INDEX idx_pr_session (session_id)
);

CREATE TABLE IF NOT EXISTS resolution_items (
    id              VARCHAR(64)  PRIMARY KEY,
    session_id      VARCHAR(64)  NOT NULL,
    ref_json        TEXT         NOT NULL,      // obra a resolver (varía según el modo, ver abajo)
    status          VARCHAR(32)  NOT NULL,      // resolved | ambiguous | not_found
    resolution_stage VARCHAR(16) NOT NULL DEFAULT 'provisional',  -- provisional | definitive
    revision        INT          NOT NULL DEFAULT 1,             -- monótono, sube en cada cambio
    normalized_json TEXT,
    resolved_json   TEXT,
    confidence      DECIMAL(6,5) NOT NULL DEFAULT 0,
    candidates_json TEXT,
    evidence_json   TEXT,
    updated_at      VARCHAR(64)  NOT NULL,
    INDEX idx_ri_session (session_id),
    INDEX idx_ri_status  (status)
);
```

### `ref_json` según el modo (punto 1)

La semántica de `resolution_items.ref_json` depende del modo de la sesión:

```
query mode:
    provider_results ──► candidatos encontrados ──► resolution_items
    (ref_json = la obra candidata que la sesión está resolviendo)

batch mode:
    works[] ──► resolution_items
    (ref_json = la obra de entrada suministrada por el usuario)
```

- **Query mode**: los `resolution_items` son los **candidatos de obra encontrados por el
  matching** sobre el universo adquirido, no obras de entrada del usuario.
- **Batch mode**: los `resolution_items` se corresponden **uno a uno con `works[]`** de la
  entrada.

### `pagination_kind` (punto 5)

`provider_results.pagination_kind` indica qué representa `cursor_value`:

```jsonc
{ "pagination_kind": "page",   "cursor_value": "3",            "next_cursor": "4" }
{ "pagination_kind": "cursor", "cursor_value": "eyJvZmZzZXQiOjEwMH0=", "next_cursor": "eyJvZmZzZXQiOjIwMH0=" }
```

No todos los proveedores se comportan igual; el almacén trata `cursor_value` como un
token opaco y `pagination_kind` solo describe su naturaleza.

### Estados de página y regla de `complete` (puntos 6 y 8)

`provider_results.status`:

- `fetched` → hemos recibido datos (`payload` disponible).
- `end_of_provider` → el proveedor confirma que no hay más páginas (`next_cursor = null`).
- `recoverable_error` → no pudimos adquirir esta página; puede reintentarse (no es fin).

**Regla de `complete`:** una sesión **no puede pasar a `complete` mientras un proveedor
incluido en el plan tenga páginas pendientes o errores recuperables**, salvo que la
política haya decidido explícitamente abandonar ese proveedor. Esto es lo que garantiza que
`complete` significa realmente *"el universo del plan está completo"*, y protege el caso
`Mozart → 490 obras` de quedar con adquisición a medias.

`UNIQUE KEY uq_pr_cursor (session_id, provider, cursor_value)` se mantiene: si el worker
se cae tras obtener una página pero antes de actualizar el estado, el reintento **no crea
otra copia** de esa página.

### Definición de `max_results_to_acquire` (punto 7)

`max_results_to_acquire` se define como el **máximo de `ProviderWork` adquiridos por
proveedor, antes del matching y de la deduplicación**. Es medible y no depende del
resultado del matcher:

```
OMR         490   (≤ 500)
IMSLP       380
MusicBrainz 120
Mutopia      70
----------------
adquiridos 1060   (el motor determina luego cuántas obras únicas representan)
```

### Separación de `max_duration_s` y `expires_at` (punto 3)

- `policy.max_duration_s` → **límite de ejecución** de la adquisición. Si se alcanza, la
  sesión termina en `partial`, pero los resultados siguen consultables.
- `expires_at` → **TTL de conservación** de la sesión. La adquisición puede terminar a los
  120 s con `partial`, y el usuario todavía puede consultar resultados durante el TTL
  (p. ej. 30 min).

### Mapeo entidad → tabla

| Entidad (resolution-store-v1) | Tabla / columnas |
|---|---|
| `resolution_sessions.*` | columnas directas; campos anidados (`query`, `providers`, `policy`, `progress`) como `*_json` |
| `provider_results.cursor` | `cursor_value` + `pagination_kind` (token opaco) |
| `provider_results.status` | `fetched` / `recoverable_error` / `end_of_provider` |
| `resolution_items.revision` | monótono (sin semántica rígida 1/2/3); `resolution_stage` separa provisional/definitivo |
| candidatos / evidencia | `candidates_json` / `evidence_json` (embebidos, **sin** tabla global `works`) |

---

## Fases de implementación

Implementación por fases, probando cada parte por separado (no un primer commit enorme).

**FASE 1 — Persistencia + HTTP sin worker**
- tablas OpStore (`_init()` + `_MemoryStore`),
- modelos de dominio (`ResolutionSession`, `ProviderResultPage`, `ResolutionItem`),
- `ResolutionSessionStore` (crear/leer sesión, listar resultados),
- endpoints: `POST` → `202` + `session_id`; `GET session` → `acquiring`; `GET results` → `[]`.

**FASE 2 — Adquisición (worker)**
- worker de `domain/jobs`,
- `AcquisitionPlan` (clasificación de consulta + cotas),
- adquisición de una página,
- persistencia idempotente (`UNIQUE KEY uq_pr_cursor`),
- reanudación (`next_cursor` / `pagination_kind`).

**FASE 3 — Matching provisional**
- reconstrucción del universo desde `provider_results`,
- matching provisional → `resolution_items` (query/batch),
- resultados paginables.

**FASE 4 — Resolución completa**
- adquisición completa (regla de `complete`),
- matching definitivo (`resolution_stage=definitive`),
- `complete` / `partial` / `failed` / `expired`,
- TTL (`expires_at`).

**FASE 5 — Optimización y métricas** (caché de repetición, si llega a ser un problema real).
