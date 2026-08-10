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
