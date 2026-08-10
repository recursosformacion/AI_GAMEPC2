# Web OSAP — Prompt de implementación: voto sobre una obra (v1)

**Estado:** PROMPT DE IMPLEMENTACIÓN. **Alcance:** solo voto. No compositores, no
administración, no modelo de obras externas.
**Base:** `docs/vote-v1-decision.md`, `docs/vote-v1-contract.md`.

---

## Rol

Ingeniero sobre osap-api (backend) y el Web OSAP (`web/`). Implementa el voto conforme al
contrato, corrigiendo los 2 bugs backend detectados y conectando el formulario de voto del Web.

---

## Alcance

- Corregir los 2 bugs backend detectados en la inspección.
- Conectar el botón/formulario de voto del Web.
- Enviar el voto a `POST /api/v1/works/{work_id}/vote`.
- Mostrar correctamente 401/403/404/409/422.
- Comprobar que el usuario autenticado puede votar.
- Pruebas end-to-end.
- **No** tocar compositores, administración ni el modelo de obras externas.

---

## 1. Corregir los 2 bugs backend

### 1.1 `StorageVoteStore.insert_vote` (`src/osap/infrastructure/persistence/storage_vote_store.py`)

- **Actual (bug):** `POST /api/v1/votes` con `work_id` en el body.
- **Debe ser:** `POST /api/v1/works/{work_id}/votes` con `work_id` **integer en la URL**,
  body `{ "user_id": <uuid>, "vote": 1..5 }`, SERVICE + `storage:write`.
- `409` → `DuplicateVoteError`; `404` → obra inexistente.

### 1.2 `StorageWorkStore.composer_id_for` (`src/osap/infrastructure/storage/work_store.py`)

- **Actual (bug):** parsea `composer_id` top-level (devuelve None).
- **Debe ser:** `GET /api/v1/works/{work_id}` y parsear **`work.composer_id`** (anidado).
  Si 404 / no resuelve → `None` → obra inexistente.

---

## 2. Conectar el botón/formulario de voto en el Web

- Añadir en la vista de obra un **selector 1..5 + botón "Votar"**.
- Solo visible si hay sesión (`useAuth.isAuthenticated()`); si no, mostrar "inicia sesión".
- Al pulsar → `apiClient.post("/works/{work_id}/vote", { vote })`.
- Estados: enviando, votado (muestra `vote_day`/valoración), error.

## 3. Mostrar los errores

| Código | UI |
|---|---|
| 401 | "Inicia sesión" (sin token) |
| 403 | "Necesitas una cuenta verificada" |
| 404 | "Obra no encontrada" |
| 409 | "Ya has votado esta obra hoy" |
| 422 | "Valoración 1..5" |

## 4. Usuario autenticado puede votar

- Solo con sesión activa; el backend valida `role=user` + `email_verified`.
- La UI no decide permisos (solo muestra/oculta).

## 5. Tests

- **Backend (unit):** corregir/ampliar tests de `StorageVoteStore` y `StorageWorkStore` con
  fake HTTP/storage (path correcto, parseo de `work.composer_id`, 409→Duplicate, 404).
- **Web (fetch mockeado):** flujo de voto exitoso y errores 401/403/404/409/422.
- **E2E:** login (usuario autenticado) → votar una obra → 201; obra inexistente → 404; ya
  votada → 409.

---

## NO hacer

- No tocar compositores, administración ni el modelo de obras externas.
- No añadir `storage:admin` al client normal.

---

## Validación

- Backend: `ruff`, `mypy`, `pytest` limpios.
- Frontend: `tsc --noEmit`, `vitest run`, `vite build`.

---

*Prompt de implementación del voto v1 (2026-08) — no implementado.*
