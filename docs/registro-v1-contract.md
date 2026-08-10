# OSAP — Contrato de Registro de usuario (Web OSAP) (v1)

**Estado:** CONTRATO (congelado). **No implementado todavía.**
**Base:** decisión `docs/registro-v1-decision.md`.
**Alcance:** registro + verificación de usuario vía osap-api → osap-auth. Sin auto-login, sin
service client, sin BD de usuarios en osap-api.

---

# 1. Frontera

```
Web OSAP ── POST /api/v1/auth/register ──► osap-api ──(proxy público)──► osap-auth
Web OSAP ── POST /api/v1/auth/verify-email ──► osap-api ──(proxy)──► osap-auth
```

- Público (no requiere token de usuario).
- osap-api **no** posee usuarios; solo proxya a osap-auth.
- **Anti-enumeración**: osap-api/osap-auth no revelan si el email ya existía.

---

# 2. Endpoints de osap-api (proxy a osap-auth)

## `POST /api/v1/auth/register`

- **Request** (relay a osap-auth):
```json
{ "email": "usuario@example.com", "password": "mínimo 8", "name": "Opcional (max 120)" }
```
- **Response 200** (relay):
```json
{ "user_id": "<uuid o null>", "verification_token": "<dev> | null", "message": "Si el email es nuevo, se ha enviado un enlace de verificación." }
```
- Semántica:
  - Email existente → misma respuesta genérica (`user_id=null`), **no** revelar.
  - Password mín 8 (validada por osap-auth).
  - `email_verified=false` tras el registro.
  - **Sin tokens** (no auto-login).

## `POST /api/v1/auth/verify-email`

- **Request**: `{ "token": "<verification_token>" }`.
- **Response 200**: `{ "message": "email verificado" }`.
- Tras verificar: `email_verified=true`.

---

# 3. Errores

| Código | Caso |
|---|---|
| 422 | Email inválido / password < 8 / payload inválido |
| 429 | Rate limit de registro (por IP) |
| 5xx | osap-auth caído (proxy) |

- **Anti-enumeración**: el email existente **no** es un error; devuelve la misma respuesta
  genérica 200.

---

# 4. Ciclo

```
Registro → usuario creado (email_verified=false)
Verificación → email_verified=true
Login → access + refresh → osap-api
```

- `email_verified=true` es una **condición de autorización** (p. ej. votar); el Web no la
  decide.

---

# 5. Web

- Formulario de registro (email, password, name) → `POST /api/v1/auth/register`.
- Tras enviar (éxito o ya existía, ambos 200 genérico): mostrar **"verifica tu email"** (no
  iniciar sesión).
- En dev, si `verification_token` llega en la respuesta, el Web puede autoverificar
  (`POST /api/v1/auth/verify-email`) o mostrar el paso de verificación.
- Después de verificar, el usuario hace **Login**.

---

# 6. Fuera de alcance

- CRUD de usuarios / roles / tier en el Web.
- Segundo sistema de credenciales.
- Tabla de usuarios en osap-api.
- Registro que escriba en storage.

---

*Contrato de Registro v1 (2026-08) — congelado; no implementado.*
