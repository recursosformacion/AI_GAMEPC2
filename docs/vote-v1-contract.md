# OSAP — Contrato del voto sobre una obra (v1)

**Estado:** CONTRATO (congelado). **No implementado aún** (solo inspección hecha).
**Base:** decisión `docs/vote-v1-decision.md`.
**Alcance:** solo voto. No compositores, no administración, no modelo de obras externas.

---

# 1. Endpoint de osap-api

## `POST /api/v1/works/{work_id}/vote`

- Requiere autenticación (Bearer user token).
- `user_id` se obtiene **solo** del token (nunca del cliente).
- `vote_day` y `voted_at` se generan en servidor (UTC).

**Request:**
```json
{ "vote": 5 }
```

**Response 201:**
```json
{
  "work_id": "2",
  "vote": 5,
  "voted_at": "2026-08-10T07:25:16Z",
  "vote_day": "2026-08-10"
}
```

## Errores

| Código | Caso |
|---|---|
| 401 | Token ausente/inválido |
| 403 | `UserPrincipal` sin `role=user` o `email_verified=false` |
| 404 | Obra inexistente |
| 409 | Ya votada esa obra ese día |
| 422 | `vote` fuera de 1..5 |

---

# 2. Backend — osap-api → osap-storage

## Resolución de obra (registro de obra externa)

`StorageWorkStore.composer_id_for(work_id)`:

- Llamada: `GET /api/v1/works/{work_id}` con SERVICE + `storage:read`.
- `work_id` es **integer** (según storage).
- Response: `{ "work": { "id": ..., "composer_id": "<uuid>", ... }, "resources": [...] }`.
- **Parsear `work.composer_id`** (anidado, no top-level).
- Si 404 / no resuelve → obra inexistente → **404**.

## Registro del voto

`StorageVoteStore.insert_vote(vote)`:

- Llamada: **`POST /api/v1/works/{work_id}/votes`** con `work_id` **integer en la URL** y SERVICE + `storage:write`.
- Body: `{ "user_id": "<uuid>", "vote": 1..5 }` (el `user_id` es dato de negocio).
- **409** de storage → `DuplicateVoteError` → **409**.
- **404** de storage → obra inexistente → **404**.

> `work_id` es integer en storage; osap-api lo usa tal cual (el formato lo define storage, no
> osap-api).

---

# 3. Web

- Botón/formulario de voto (selector 1..5 + "Votar") en la obra.
- Llama `POST /api/v1/works/{work_id}/vote` con `Authorization: Bearer <access_token>`.
- Solo visible con sesión; la seguridad la aplica osap-api.
- Mostrar correctamente: **401** (pedir login), **403** (cuenta verificada necesaria),
  **404** (obra no encontrada), **409** (ya votada hoy), **422** (1..5).

---

# 4. Reglas

- Escala 1..5; `0`/`6` → 422.
- Un voto por obra y día (UNIQUE en storage) → 409.
- `user_id` del token como dato de negocio; nunca del cliente.
- Identidad de servicio: SERVICE + `storage:write` (client normal, sin `storage:admin`).

---

# 5. Alcance fuera

- No se tocan compositores, administración ni el modelo de obras externas.

---

*Contrato del voto v1 (2026-08) — congelado; no implementado.*
