# OSAP — vote-v1 (consolidado)


## Parte: vote-v1-decision.md

---

# OSAP — Flujo de voto sobre una obra (decisión v1)

**Estado:** DECISIÓN ARQUITECTÓNICA (a congelar). **No implementado todavía.**
**Objeto:** cerrar la decisión del flujo de voto, en especial el **registro de obra externa**
(cómo osap-api confirma la obra y obtiene su `composer_id` vía storage), antes de escribir el
contrato y el prompt.

---

# 1. Objetivo

Un usuario autenticado vota una obra (escala 1..5). El voto se registra en **osap-storage**
con el `user_id` como **dato de negocio**. osap-api autentica y autoriza; no persiste votos.

Flujo de extremo a extremo a verificar:

```
usuario ──(user JWT)──► osap-auth ──► osap-api ──► autorización ──► osap-storage ──► registro del voto
```

---

# 2. Hechos de los contratos actuales

- osap-api ya implementa el voto (backend): `POST /api/v1/works/{work_id}/vote`
  (require_can_vote → UserPrincipal + role=user + email_verified), valida escala 1..5, resuelve
  `composer_id` vía `IWorkStore`, y delega en `IVoteStore` (`StorageVoteStore` con
  SERVICE + `storage:write`).
- osap-auth emite user tokens con `token_use=user`, `sub`, `roles`, `email_verified`.
- osap-storage es el propietario de `work_votes` (regla 1 voto/obra/día en su BD) y de las
  estadísticas de obra/compositor. El `user_id` viaja como dato de negocio; storage no resuelve
  al usuario.
- Existe una asimetría de identidad de obra: `work_id` (formato que define storage) frente al
  identificador que el Web recibe en los resultados de búsqueda.

---

# 3. Decisión congelada — flujo de voto

## 3.1 Flujo

```
usuario (user JWT)
  │
  ▼
osap-api
  ├─ resuelve UserPrincipal (token_use=user, sub, roles, email_verified)
  ├─ autoriza: role=user + email_verified=true   → si no: 401/403
  ├─ valida la obra y obtiene composer_id vía contrato de storage  → si no existe: 404
  ├─ valida la escala 1..5   → si no: 422
  │
  │ SERVICE + storage:write
  ▼
osap-storage
  └─ registra el voto (user_id como dato de negocio; UNIQUE(1/obra/día) → 409)
```

## 3.2 Registro de obra externa (decisión clave)

- La **obra vive en osap-storage**; osap-api **no** tiene catálogo propio de obras.
- Para votar, osap-api **confirma la existencia** de la obra y obtiene su **`composer_id`**
  mediante el **contrato de storage** (endpoint de resolución de obra), sin acceder a la BD de
  storage ni inventar catálogo.
- El `composer_id` se usa para la agregación de estadísticas de compositor en storage.
- Si la obra no existe (storage no la resuelve) → **404**.
- **Formato del identificador**: osap-api usa el `work_id` tal y como lo define/expone storage
  (asimetría string/int resuelta por el contrato de storage, no por osap-api).

## 3.3 Reglas del voto

| Regla | Respuesta |
|---|---|
| Escala 1..5 | 0 ó 6 → **422** |
| Sin token / token inválido | **401** |
| Sin role=user o email_verified=false | **403** |
| Obra inexistente | **404** |
| Ya votada esa obra ese día | **409** (UNIQUE en storage) |

- `user_id` se toma **solo** del token; el cliente nunca lo envía.

## 3.4 Autorización (osap-api)

- Votar exige `UserPrincipal` con `role=user` y `email_verified=true`.
- La UI solo muestra el botón de voto si hay sesión; la seguridad la aplica osap-api.

## 3.5 Identidad de servicio

- osap-api → osap-storage con **SERVICE + `storage:write`** (client normal de osap-api).
- **NO** se usa `storage:admin` para votar.

---

# 4. Resolución de obra (inspección — RESUELTO)

## Endpoint existente en osap-storage

**`GET /api/v1/works/{work_id}`** (`work_id` = **integer**)

- **200** → `{ "work": { "id": 2, "composer_id": "<uuid>", "composer": "A N", ... }, "resources": [...] }`.
- **404** → obra inexistente.
- Devuelve `composer_id` anidado en `work.composer_id`.

**No hace falta crear ningún endpoint**: storage ya resuelve `work_id → composer_id`.

## Votar una obra inexistente

`POST /api/v1/works/{work_id}/votes` → **404** `{"detail": "work with id 99999 not found"}`.

## Qué espera realmente el voto (IVoteStore/StorageVoteStore)

- Endpoint real del voto: **`POST /api/v1/works/{work_id}/votes`** con `work_id` **integer en la URL** y body `{ "user_id": "...", "vote": 1..5 }`.
- **Asimetría detectada en los clientes actuales de osap-api** (a corregir en la implementación):
  1. `StorageVoteStore.insert_vote` hace `POST /api/v1/votes` (path incorrecto) y envía `work_id` en el body; debe ser `POST /api/v1/works/{work_id}/votes` con `work_id` en la URL.
  2. `StorageWorkStore.composer_id_for` llama a `GET /api/v1/works/{work_id}` (path correcto) pero **parsea mal** la respuesta: espera `composer_id` top-level, y en storage está anidado en `work.composer_id`.

> Con esto queda cerrada esta parte: la resolución de obra externa usa el endpoint existente de
> storage; no se crea ningún endpoint nuevo.

---

# 5. No implementar todavía

- No se implementa el voto en el frontend aún (se conectará tras cerrar contrato/prompt).
- No se crea catálogo de obras en osap-api.
- No se añade `storage:admin` al client normal.

---

*Decisión del flujo de voto v1 (2026-08) — pendiente de aprobación; no implementado.*



## Parte: vote-v1-contract.md

---

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



## Parte: implementation-prompt-web-vote-v1.md

---

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



