# Resolution Store v1 — Modelo de datos, ciclo de vida y persistencia

> Diseño del almacén de resolución de osap-api, posterior al ADR-0033
> (`docs/osap/adr/0033-resolution-sessions.md`). Congela la **arquitectura de datos**:
> entidades, identidad de página, garantías, ciclo de vida y persistencia. **No** define
> aún la implementación física (JSON, columnas, etc.) ni el SQL.

> **Estado: congelado como Resolution Store v1.** El siguiente paso es el **contrato HTTP
> exacto + esquema SQL** de las tres tablas, donde se empieza a convertir esta
> arquitectura en código.

## Frontera (no violable)

```
osap-api / OpStore
│
├── resolution_sessions   → una operación concreta
├── provider_results      → lo adquirido durante ESA operación
└── resolution_items      → resultados derivados de ESA operación
```

y no:

```
osap-api
└── works   ❌ catálogo paralelo
```

Los candidatos quedan **embebidos por ítem**, nunca en una tabla global `works`.

## Identidad de una página adquirida

Una página adquirida se identifica de forma única por:

```
(session_id, provider, cursor)
```

Donde:

- `session_id`: la `ResolutionSession` a la que pertenece.
- `provider`: el proveedor (OMR, IMSLP, MusicBrainz, Mutopia, …).
- `cursor`: el **token de paginación del proveedor**.

`cursor` es formalmente la **identidad del mecanismo de paginación del proveedor**: no se
asume que sea numérico. Para unos será `page=3`; para otros un **cursor opaco** (token,
continuation key, etc.). El almacén solo lo trata como un valor opaco y único por
proveedor.

Esta clave es lo que garantiza:

- **No descargar dos veces la misma página** dentro de una sesión: la inserción es
  idempotente por `(session_id, provider, cursor)`.
- **Poder reanudar**: cada `provider_results` conserva el siguiente cursor; se retoma
  desde el último obtenido.
- **Saber qué páginas se han adquirido**: `provider_results` es el registro exacto.
- **Conservar el cursor siguiente**: cada `provider_results` guarda `next_cursor`.
- **Distinguir `complete` de `partial`**: ver el estado `end_of_provider` y la comparación
  contra el plan de adquisición.
- **Volver a ejecutar el matching sin llamar al proveedor**: el `payload` de la página es
  suficiente para reconstruir el universo y re-resolver.

## Qué guardamos de la respuesta del proveedor

Guardamos **lo suficientemente completo para volver a hacer matching sin volver a
consultar al proveedor**. Eso es el contrato normalizado `ProviderWork`
(`src/osap/infrastructure/providers/contracts.py`, ver `docs/osap/providers-layer.md`):

- **Identity**: id y claves del proveedor.
- **Metadata**: título, compositor, catálogo, año, subtítulo…
- **Statistics**: confianza/estadísticas que aporta el proveedor.
- **Resources**: referencias/`links` a las partituras (se conservan para una descarga
  posterior sin re-consultar).

Al guardar el `ProviderWork` ya normalizado, el pipeline
`Canonicalizer → Matcher → Ranking → Work Resolution` puede consumir el mismo payload
almacenado, sin conocer cómo respondió el proveedor. La decisión de si físicamente es
JSON, varias columnas, etc., queda para la implementación.

## Entidades

### `resolution_sessions` — una operación concreta

| Atributo | Descripción |
|---|---|
| `session_id` | Identificador único de la sesión (devuelto en el `202`). |
| `status` | `acquiring` / `resolving` / `complete` / `partial` / `failed` / `expired`. |
| `query` | La consulta original (compositor, título, catálogo, fuente) o texto libre. |
| `acquisition_plan` | Proveedores implicados + perfiles/cotas por proveedor, derivados de la clasificación de la consulta. |
| `policy` | Instantánea de los límites configurables aplicados (`max_results_to_acquire`, `max_pages_per_provider`, `max_duration`). |
| `progress` | Contadores: páginas adquiridas, obras adquiridas, ítems resueltos. |
| `created_at` / `updated_at` / `expires_at` | Ciclo de vida y TTL. |
| `error` | Mensaje si terminó en `failed`. |

### `provider_results` — lo adquirido durante ESA operación

| Atributo | Descripción |
|---|---|
| `id` | Identificador de la fila. |
| `session_id` | FK a la sesión. |
| `provider` | Proveedor (OMR, IMSLP, MusicBrainz, Mutopia, …). |
| `cursor` | Token de paginación del proveedor (opaco; puede ser `page=N` o un cursor). |
| `next_cursor` | Cursor para la siguiente página (reanudar); `null` si no hay más. |
| `acquired_at` | Cuándo se obtuvo. |
| `status` | `fetched` / `recoverable_error` / `end_of_provider` (ver abajo). |
| `payload` | Lista de `ProviderWork` normalizados (suficiente para re-resolver). |
| `meta` | Datos del transporte (estado HTTP, etag, etc.). |

**Unicidad:** `(session_id, provider, cursor)` — una página se adquiere una sola vez.

### Estado de una página

`provider_results.status` distingue tres casos:

- `fetched`: página adquirida con éxito; `payload` disponible.
- `recoverable_error`: página que falló de forma **recuperable** (timeout, 5xx): se puede
  reintentar; no es fin de proveedor.
- `end_of_provider`: el proveedor indicó que **no hay más páginas** (`next_cursor = null`).

Esto permite saber si `complete` significa realmente *"el proveedor terminó"* (`EOF` por
cada proveedor del plan) o simplemente *"dejamos de intentar"* (`partial` o
`recoverable_error` pendientes). Sin este estado, sería imposible distinguir ambos casos.

### `resolution_items` — resultados derivados de ESA operación

| Atributo | Descripción |
|---|---|
| `id` | Identificador del ítem. |
| `session_id` | FK a la sesión. |
| `ref` | La obra de entrada (compositor, título, catálogo, `source_provider`, `source_work_id`). |
| `status` | Estado **de esa obra**: `resolved` / `ambiguous` / `not_found`. |
| `normalized` | Formas comparables (`title_raw`, `title`, `composer_raw`, `composer`, `catalog`). |
| `resolved` | Conclusión: `work` y `composer` (puede ser `null`). |
| `confidence` | Confianza de la resolución. |
| `candidates` | Candidatos **embebidos** (no tabla global). |
| `evidence` | Evidencias por proveedor. |
| `revision` | Número de versión del resultado: `1` provisional, `2` provisional mejorado, `3` definitivo (ver abajo). |
| `updated_at` | Cuándo se actualizó por última vez (permite reconstruir el momento). |

## Ciclo de vida y dos niveles de matching

1. **Creación**: `POST /works/resolve` crea la sesión (`acquiring`), guarda `query` y el
   `acquisition_plan`, y devuelve `202` + `session_id`.
2. **Adquisición**: el worker de `domain/jobs` recoge sesiones en `acquiring`, obtiene
   páginas según el plan y las persiste en `provider_results` (idempotente por clave de
   página). Al completar el plan (EOF por cada proveedor) pasa a `resolving`.
3. **Matching provisional**: sobre el universo adquirido hasta ahora; se crean/actualizan
   `resolution_items` con `revision` baja (la Web los puede mostrar como "adquiriendo…").
4. **Matching definitivo**: adquisición completa; se re-ejecuta el matching sobre el
   universo completo en `OpStore` (sin consultar a los proveedores) y se actualizan los
   `resolution_items` con la `revision` definitiva.
5. **Terminal**: `complete`, o `partial` (se alcanzaron límites o quedan errores
   recuperables pendientes), `failed` o `expired` (TTL). El TTL limpia la sesión y sus
   filas salvo que se retenga por valor histórico.

### Semántica de `revision` (sin tabla de revisiones)

`resolution_items.revision` indica qué versión representa el **registro actual**:

- `1` → provisional (primer matching con universo parcial).
- `2` → provisional mejorado (más adquisición, matching re-ejecutado).
- `3` → definitivo (universo completo).

No hace falta una tabla de revisiones todavía: el registro actual guarda la revisión y
`updated_at` permite reconstruir el momento (auditoría mínima). Si más adelante se quiere
historial completo, se añade una tabla aparte sin romper esto.

### Orden-independencia de la adquisición

**El orden de llegada de las páginas no debe afectar al resultado final.** Si OMR entrega
las páginas 1, 2, 3 y 4 en distinto orden (p. ej. por un reinicio), el universo
reconstruido debe ser el mismo y el matching definitivo debe producir el mismo resultado.

Consecuencia de diseño:

- El universo se **reconstruye** a partir de `provider_results` (no de un estado mutable
  acumulado durante la adquisición).
- El matching definitivo opera sobre esa reconstrucción determinista.
- Así, la idempotencia de `(session_id, provider, cursor)` + reconstrucción del universo
  hacen que adquisición, orden de llegada y reanudación no alteren el resultado.

## Garantías resumidas

- **Idempotencia de adquisición**: `(session_id, provider, cursor)` → nunca dos veces.
- **Cursor opaco**: `cursor` es el token de paginación del proveedor (numérico u opaco);
  el almacén no asume formato.
- **Estado de página explícito**: `fetched` / `recoverable_error` / `end_of_provider`, para
  saber si `complete` significa *"el proveedor terminó"* o *"dejamos de intentar"*.
- **Orden-independencia**: el orden de llegada de las páginas no altera el universo ni el
  matching definitivo (el universo se reconstruye desde `provider_results`).
- **Reanudación**: `next_cursor` por proveedor → continuar tras un timeout/reinicio.
- **Re-resolución sin proveedor**: el `payload` (`ProviderWork`) permite reconstruir el
  universo y re-ejecutar `Canonicalizer → Matcher → Ranking → Work Resolution`.
- **Estado no ambiguo**: estado de sesión y estado de obra son independientes (ADR-0033).
- **Sin catálogo paralelo**: candidatos embebidos, sin tabla global `works`.
- **Provisional ≠ definitivo**: `revision` (1 provisional / 2 mejorado / 3 definitivo) +
  `updated_at` permiten distinguirlos sin una tabla de revisiones.

## Flujo (vista de usuario)

La Web **nunca espera** a que la adquisición/resolución termine:

```
POST /works/resolve ──► 202 { session_id }
GET /sessions/{id}   ──► estado + progreso + contadores
GET /sessions/{id}/results?page=1 ──► resultados (provisionales o definitivos)

mientras el worker sigue adquiriendo y re-resolviendo en segundo plano.
```

En lugar de `OMR → página 1 → presentar → fusionar → fin`, el flujo es
`OMR páginas 1..N → provider_results → universo adquirido → ranking/fusión`, y se pueden
mostrar resultados provisionales sin afirmar que son definitivos.

## Pendiente (no este documento)

- Implementación física (JSON vs columnas), migraciones y esquema SQL concreto.
- Contratos exactos de `POST /works/resolve`, `GET /sessions/{id}` y
  `GET /sessions/{id}/results`.
- Clasificación de la consulta → `acquisition_plan` con perfiles de cotas.
