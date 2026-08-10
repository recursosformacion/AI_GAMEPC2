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
