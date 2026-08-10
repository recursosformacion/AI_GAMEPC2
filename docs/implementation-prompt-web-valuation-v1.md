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
