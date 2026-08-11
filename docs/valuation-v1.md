# OSAP — valuation-v1 (consolidado)


## Parte: valoracion-v1-decision.md

---

# OSAP — Valoración (estadísticas agregadas) — decisión v1

**Estado:** DECISIÓN ARQUITECTÓNICA (a congelar). **No implementado todavía.**
**Objeto:** cerrar qué es "Valoración" y cómo se expone, **reutilizando** las estadísticas que
ya calcula osap-storage (sin inventar otro modelo).

---

# 1. Distinción voto vs valoración

- **Voto**: la valoración **numérica individual** 1..5 que un usuario da a una obra (ya cerrado).
- **Valoración**: las **estadísticas agregadas** de esas votaciones (media, nº de votos,
  valoración de obra/compositor). Esta es la pieza que abrimos ahora.

> El voto es la entrada (dato individual). La valoración es la salida agregada que expone
> osap-api y consume el Web.

---

# 2. Hechos del contrato existente (osap-storage)

osap-storage ya calcula y expone (proceso nocturno de agregación):

## `GET /api/v1/works/{work_id}/statistics`
```json
{ "work_id": 2, "rating": 4.32, "adjusted_rating": 4.1, "vote_count": 37,
  "work_count": 1, "confidence": 0.95, "calculated_at": "..." }
```

## `GET /api/v1/composers/{composer_id}/statistics`
```json
{ "composer_id": "comp", "rating": 4.41, "adjusted_rating": 4.3, "vote_count": 1523,
  "work_count": 264, "confidence": 0.9, "calculated_at": "..." }
```

- `rating` = media ponderada de los votos (la **valoración**).
- `vote_count` = nº de votos; `work_count` = nº de obras agregadas; `confidence`, `calculated_at`.
- La agregación la hace **storage** (no osap-api).

---

# 3. Decisión congelada — Valoración

## Definición

**Valoración = estadísticas agregadas de votos para una obra o compositor**, calculadas por
osap-storage y expuestas por osap-api.

## Exposición (osap-api)

osap-api **reutiliza** los endpoints de storage, exponiendo sus campos sin inventar modelo:

- `GET /api/v1/works/{work_id}/statistics` → devuelve `rating` (valoración), `vote_count`,
  `work_count`, `confidence`, `calculated_at`.
- `GET /api/v1/composers/{composer_id}/statistics` → idem por compositor.

## Acceso

| Recurso | ANONYMOUS | USER | ADMIN |
|---|---|---|---|
| Estadísticas de obra | ✅ | ✅ | ✅ |
| Estadísticas de compositor | ✅ | ✅ | ✅ |

- Público (lectura). Sin autenticación de usuario; la llamada a storage va con
  SERVICE + `storage:read`.

## Sin votos

- `vote_count = 0`, `rating = null` (nunca `0` como valoración).

---

# 4. Distribución 1–5 (pendiente, fuera de v1)

- La **distribución de votos 1–5** (histograma) **no** está en el contrato actual de storage
  (solo `rating`/`vote_count`). Requeriría añadirla en **osap-storage** (contrato de storage),
  que está **fuera del alcance de osap-api**.
- Se deja **pendiente** para una fase posterior; la valoración v1 usa `rating`/`vote_count`.

---

# 5. No implementar todavía

- No se implementa el frontend de Valoración aún.
- No se crea modelo nuevo de estadísticas en osap-api.
- No se modifica osap-storage.

---

*Decisión de Valoración v1 (2026-08) — pendiente de aprobación; no implementado.*



## Parte: valuation-v1-contract.md

---

# OSAP — Contrato de Valoración (estadísticas agregadas) (v1)

**Estado:** CONTRATO (congelado). **No implementado todavía.**
**Base:** decisión `docs/valoracion-v1-decision.md`.
**Alcance:** solo lectura de estadísticas agregadas de obra/compositor. Sin distribución 1–5.
osap-api hace **proxy** de osap-storage (no recalcula ni transforma).

---

# 1. Endpoints de osap-api

- `GET /api/v1/works/{work_id}/statistics`
- `GET /api/v1/composers/{composer_id}/statistics`

## Shapes exactos

### Work
```json
{
  "work_id": "2",
  "rating": 4.32,
  "adjusted_rating": 4.1,
  "vote_count": 37,
  "work_count": 1,
  "confidence": 0.95,
  "calculated_at": "2026-08-10T10:00:00Z"
}
```

### Composer
```json
{
  "composer_id": "comp",
  "rating": 4.41,
  "adjusted_rating": 4.3,
  "vote_count": 1523,
  "work_count": 264,
  "confidence": 0.9,
  "calculated_at": "2026-08-10T10:00:00Z"
}
```

---

# 2. Semántica

- `rating` es **nullable** cuando `vote_count = 0` (`rating = null`, nunca `0`).
- `adjusted_rating` debe quedar definido explícitamente cuando no hay votos, **si el contrato de
  storage lo permite** (si storage lo devuelve `null`, osap-api lo relay como `null`).
- **osap-api hace proxy**: expone los valores de storage tal cual, sin recalcular ni
  transformar. No inventa `rating` si storage devuelve `null`.

---

# 3. Autorización

| Recurso | ANONYMOUS | USER | ADMIN |
|---|---|---|---|
| Estadísticas de obra | ✅ | ✅ | ✅ |
| Estadísticas de compositor | ✅ | ✅ | ✅ |

- Lectura pública (sin autenticación de usuario).
- osap-api → osap-storage con el **service client normal** + `storage:read`.
- **Nunca** `storage:admin`.

---

# 4. Errores

| Código | Caso |
|---|---|
| 404 | Obra inexistente / compositor inexistente |
| 503 | Error de storage / identidad de servicio no configurada (patrón ya usado en compositores/voto) |

- **No** introducir errores de negocio que storage no tenga.
- Mapear los errores de storage según el patrón existente (503 para fallo de infraestructura).

---

# 5. Frontend

- Mostrar la **valoración de obra** y de **compositor**.
- **No** mostrar distribución 1–5.
- **No inventar** valoración cuando `rating = null` (mostrar "sin valoraciones" o equivalente).

---

# 6. Relación con el voto

- Tras votar correctamente, el Web puede **volver a consultar** las estadísticas.
- **Importante:** la agregación de storage es **nocturna**; **no** prometer que la valoración
  cambie inmediatamente tras un voto. **Un voto 201 no implica que la valoración cambie en ese
  momento.**

---

# 7. Fuera de alcance

- Distribución 1–5 (requiere contrato de osap-storage).
- Creación/edición de obras o compositores.
- `tier`.

---

*Contrato de Valoración v1 (2026-08) — congelado; no implementado.*



## Parte: implementation-prompt-web-valuation-v1.md

---

# Web OSAP — Prompt de implementación: Valoración (estadísticas agregadas) (v1)

**Estado:** PROMPT DE IMPLEMENTACIÓN. **Alcance:** solo lectura de valoración (estadísticas de
obra/compositor). Sin distribución 1–5.
**Base:** `docs/valoracion-v1-decision.md`, `docs/valuation-v1-contract.md`.

---

## Rol

Ingeniero sobre osap-api (backend) y el Web OSAP (`web/`). Implementa la valoración conforme al
contrato. osap-api hace **proxy** de osap-storage (sin recalcular).

---

## 1. Backend — endpoints de estadísticas

Alinear osap-api con el contrato (proxy de storage):

- `GET /api/v1/works/{work_id}/statistics` → shape `{work_id, rating, adjusted_rating,
  vote_count, work_count, confidence, calculated_at}`.
- `GET /api/v1/composers/{composer_id}/statistics` → shape `{composer_id, rating,
  adjusted_rating, vote_count, work_count, confidence, calculated_at}`.

- Actualizar los DTOs actuales (hoy `vote_count`/`vote_average`) al shape del contrato.
- `StorageVoteStore.work_statistics` / `composer_statistics` deben **relayar** los campos de
  storage (no recalcular). `rating` nullable; `adjusted_rating` según storage.
- No transformar valores; si storage devuelve `null`, se relay `null`.

## 2. Errores

- Obra inexistente → **404**.
- Compositor inexistente → **404**.
- Error de storage / identidad de servicio no configurada → **503** (patrón de
  compositores/voto).
- No introducir errores de negocio que storage no tenga.

## 3. Autorización

- Lectura pública (ANONYMOUS/USER/ADMIN).
- osap-api → storage con SERVICE + `storage:read` (client normal). Nunca `storage:admin`.

## 4. Frontend — mostrar valoración

- En la obra: mostrar `rating` (si no es `null`) y `vote_count`; si `rating = null`, mostrar
  "sin valoraciones" (no inventar).
- En el compositor: mostrar `rating`/`vote_count` del compositor.
- **No** mostrar distribución 1–5.
- Tras votar, el Web **puede volver a consultar** las estadísticas; **no** asumir que la
  valoración cambia de inmediato (agregación nocturna).

## 5. Tests

- Backend: `StorageVoteStore.work_statistics`/`composer_statistics` relayan `rating`,
  `adjusted_rating`, `vote_count`, `work_count`, `confidence`, `calculated_at` (fake HTTP).
- Web: mostrar rating; `rating=null` → "sin valoraciones"; no distribución.
- E2E: obra/compositor existentes → 200 con el shape; inexistentes → 404; storage caído → 503.

## 6. NO hacer

- No calcular distribución 1–5.
- No recalcular valoración en osap-api (proxy).
- No tocar osap-storage.
- No `storage:admin`.

## 7. Validación

- Backend: `ruff`, `mypy`, `pytest` limpios.
- Frontend: `tsc --noEmit`, `vitest run`, `vite build`.

---

*Prompt de implementación de Valoración v1 (2026-08) — no implementado.*



