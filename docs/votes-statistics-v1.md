# OSAP-API — Votos y estadísticas (v1)

**Estado:** v1.
**Depende de:** `osap-auth` (identidad de usuario) y `osap-storage` (`composer_id` y
**persistencia de votos**).

---

# 1. Principio arquitectónico

**osap-api es responsable de:**

- Recibir votos, comprobar autenticación, aplicar la regla de votación y **enviarlos a
  osap-storage** para su persistencia.
- Leer y exponer estadísticas agregadas de **Work** y de **compositor** (por `composer_id`).
- Procesar el evento `user.deleted` (ordenar la anonimización a storage).

**osap-api NO es responsable de:**

- Gestionar usuarios, contraseñas, verificar emails o resolver identidades (eso es `osap-auth`).
- Resolver nombres/aliases/fusionar compositores ni modificar la identidad de una Work
  (eso es `osap-storage`).
- Conocer detalles internos de Storage ni acceder a su BD.
- **Persistir los votos en una BD propia**: los votos se guardan en **osap-storage**.

La identidad del usuario es exclusivamente el `user_id` (UUID) del access token. La
identidad de compositor es el `composer_id` que Storage proporciona en cada Work.

> **Almacenamiento:** osap-api **no tiene BD de votos**. El esquema (`work_votes`,
> `work_statistics`, `composer_statistics`, `stats_executions` y el índice
> `UNIQUE(user_id, work_id, vote_day)`) vive en **osap-storage**. osap-api delega
> mediante ``StorageVoteStore`` (contrato de Storage).
>
> **Proceso nocturno y recalculo completo:** pertenecen a **osap-storage**. osap-api solo
> lee/expone los agregados que storage mantiene.

---

# 2. Modelo de voto (en osap-storage)

Tabla `work_votes` (pertenece a storage):

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | clave primaria |
| `user_id` | UUID opaco | `NULL` tras anonimización; nunca PII |
| `work_id` | TEXT | identificador de Work |
| `composer_id` | TEXT | denormalizado (de Storage) para estadísticas |
| `vote` | INTEGER | escala 1..5 |
| `voted_at` | TEXT | fecha/hora UTC |
| `vote_day` | TEXT | día UTC para la restricción diaria |
| `anonymized` | INTEGER | 0 identificado, 1 anonimizado |

## Regla

> **Un usuario puede votar una obra como máximo una vez al día (UTC).** Puede votar
> varias obras el mismo día. `vote_day` se calcula en **servidor** (UTC).

```text
UNIQUE(user_id, work_id, vote_day)
```

La restricción vive en la **BD de Storage** (no solo `SELECT→INSERT`), por lo que dos
peticiones concurrentes no generan dos votos: el conflicto se traduce en **HTTP 409**.

## Escala

| Valor | Significado |
|---|---|
| 1 | Muy mala |
| 2 | Mala |
| 3 | Normal |
| 4 | Buena |
| 5 | Excelente |

---

# 3. Contrato de Storage para votos (lo que osap-api consume)

osap-api (vía `StorageVoteStore`) llama a osap-storage:

| Operación | Endpoint (Storage) |
|---|---|
| Registrar voto | `POST /api/v1/votes` (409 si duplicado) |
| Estadísticas de Work | `GET /api/v1/works/{work_id}/statistics` |
| Estadísticas de compositor | `GET /api/v1/composers/{composer_id}/statistics` |
| Anonimizar usuario | `POST /api/v1/votes/anonymize` |
| Total de votos | `GET /api/v1/votes/overview` |
| Top Works / Compositores | `GET /api/v1/votes/top-works`, `/top-composers` |
| Última ejecución | `GET /api/v1/votes/executions/last` |

El esquema SQL de las tablas vive en **osap-storage**; no hay migraciones de votos en
osap-api.

---

# 4. Votación

## `POST /api/v1/works/{work_id}/vote`

Requiere autenticación. El `user_id` **nunca** viene del cliente; se obtiene del access
token. `voted_at` y `vote_day` se generan en servidor (UTC).

```json
// Request
{ "vote": 5 }

// Response 201
{
  "success": true,
  "data": { "work_id": "w1", "vote": 5, "voted_at": "2026-08-06T10:00:00Z", "vote_day": "2026-08-06" }
}
```

### Errores

| Código | Significado |
|---|---|
| 401 | Token ausente/inválido |
| 404 | Work inexistente |
| 422 | `vote` fuera de 1..5 |
| 409 | Ya votó esa obra ese día |

---

# 5. Estadísticas de Work

Tabla agregada `work_statistics` (`work_id`, `vote_count`, `vote_sum`, `vote_average`,
`updated_at`). `vote_sum` es dato interno para el cálculo; la API no lo devuelve.

## `GET /api/v1/works/{work_id}/statistics`

```json
{
  "success": true,
  "data": { "work_id": "w1", "vote_count": 37, "vote_average": 4.32 }
}
```

Sin votos: `vote_count = 0`, `vote_average = null` (nunca `0` como valoración).

---

# 6. Estadísticas de compositor

Tabla agregada `composer_statistics` (`composer_id`, `vote_count`, `vote_sum`,
`vote_average`, `updated_at`).

La relación conceptual es `Work → composer_id → Composer`. osap-api no resuelve el
nombre del compositor; solo agrega por `composer_id`.

## `GET /api/v1/composers/{composer_id}/statistics`

```json
{
  "success": true,
  "data": { "composer_id": "mozart", "vote_count": 1523, "vote_average": 4.41 }
}
```

### Agregación ponderada

La estadística de un compositor se calcula **a partir de los votos originales** de sus
obras (no una media de medias):

```text
vote_count   = nº de votos de las obras del compositor
vote_sum     = Σ de esos votos
vote_average = vote_sum / vote_count
```

---

# 7. `user.deleted`

osap-api se suscribe al evento `user.deleted` de osap-auth (`{ user_id, deleted_at }`):

1. Anonimiza los votos del `user_id` (`user_id=NULL`, `anonymized=1`).
2. Conserva el dato estadístico (el voto sigue contando en el agregado).
3. Recalcula los agregados afectados (obras + compositores).

El modelo distingue **voto identificado** (`anonymized=0`) de **voto anonimizado**
(`anonymized=1`) sin guardar PII (no email ni datos personales en `work_votes`).

---

# 8. Concurrencia y seguridad

- `UNIQUE(user_id, work_id, vote_day)` en la BD → conflicto de concurrencia = 409.
- El cliente no puede enviar `user_id`, `voted_at` ni `vote_day` (se ignoran y se generan
  en servidor).
- Votar exige autenticación (401 si no hay token válido).
- osap-api no accede a la BD de osap-auth ni a la de osap-storage.

---

# 9. Administración

`GET /api/v1/admin/votes` (autenticado) devuelve:

```json
{
  "success": true,
  "data": {
    "total_votes": 1523,
    "top_works":    [ { "work_id": "w1", "vote_count": 37, "vote_average": 4.32 } ],
    "top_composers": [ { "composer_id": "mozart", "vote_count": 1523, "vote_average": 4.41 } ],
    "last_execution": { "kind": "recompute", "status": "ok", "started_at": "...", "finished_at": "..." }
  }
}
```

La autorización administrativa usa el sistema de autorización existente (claim `roles`
del token cuando el JWKS real esté cableado); no se crea un sistema de roles nuevo.

---

# 10. Recálculo y fusión

- El **recálculo** de `work_statistics` / `composer_statistics` desde `work_votes` es
  responsabilidad de **osap-storage** (proceso nocturno y recalculo completo).
- osap-api envía el **`composer_id` vigente** que Storage proporciona en el momento del
  voto; tras una **fusión de compositor**, Storage re-agrega usando el compositor
  destino en su recálculo.

---

# 11. Ejemplos JSON

Voto + estadísticas de Work + estadísticas de compositor:

```json
POST /api/v1/works/KV618/vote
{ "vote": 5 }
→ 201 { "data": { "work_id": "KV618", "vote": 5, "voted_at": "2026-08-06T10:00:00Z", "vote_day": "2026-08-06" } }

GET /api/v1/works/KV618/statistics
→ 200 { "data": { "work_id": "KV618", "vote_count": 37, "vote_average": 4.32 } }

GET /api/v1/composers/mozart/statistics
→ 200 { "data": { "composer_id": "mozart", "vote_count": 1523, "vote_average": 4.41 } }
```
