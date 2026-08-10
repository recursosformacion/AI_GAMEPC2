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
