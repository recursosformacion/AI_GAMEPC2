# OSAP — registro-v1 (consolidado)


## Parte: registro-v1-decision.md

---

# OSAP — Registro de usuario (Web OSAP) — decisión v1

**Estado:** DECISIÓN APROBADA. **No implementado.**
**Base:** osap-auth es la autoridad de identidad. **No se crea** tabla de usuarios en osap-api,
registro paralelo, endpoint que escriba en storage, segundo sistema de credenciales, ni roles/
tier en el Web.
**Objeto:** cerrar cómo el Web OSAP registra usuarios vía osap-auth (inspección del contrato de
registro hecha).

---

# 1. Frontera

```
Web OSAP
   │
   │ email + password + datos de registro
   ▼
osap-api
   │
   │ llamada al endpoint público de osap-auth
   ▼
osap-auth
   │
   └── crea usuario
```

- **No** interviene un service client: es una operación de **usuario/identidad**, no entre
  servicios.
- osap-api **no** crea usuarios directamente en la BD de osap-auth.
- osap-auth sigue siendo la **autoridad de identidad**.
- **El Web no conoce directamente la infraestructura de osap-auth**; osap-api proxya.
- **Anti-enumeración**: el Web **tampoco** debe revelar si el email ya existía (misma respuesta
  genérica para "creado" y "ya existe").

---

# 2. Registro ≠ verificación ≠ autenticación

Ciclo completo:

```
         ┌──────────────┐
         │  Registro    │  POST /register
         └──────┬───────┘
                │
                ▼
          usuario creado
          email_verified=false
                │
                ▼
         ┌──────────────┐
         │ Verificación │  POST /verify-email
         └──────┬───────┘
                │
                ▼
          email_verified=true
                │
                ▼
         ┌──────────────┐
         │    Login     │  POST /login
         └──────┬───────┘
                │
                ▼
          access + refresh
                │
                ▼
             osap-api
```

- `email_verified=true` es una **condición de autorización** (p. ej. para votar); **no** es algo
  que el Web pueda decidir.

---

# 3. Contrato de registro de osap-auth (inspección)

## `POST /auth/register`

**Request:**
```json
{ "email": "usuario@example.com", "password": "mínimo 8", "name": "Opcional (max 120)" }
```

**Response 200:**
```json
{ "user_id": "<uuid o null>", "verification_token": "<dev> | null", "message": "Si el email es nuevo, se ha enviado un enlace de verificación." }
```

## Semántica

| Aspecto | Contrato |
|---|---|
| Email existente | **200 genérico** (`user_id=null`, mismo mensaje) — anti-enumeración; no revela si existe |
| Password | **mínimo 8** caracteres (`validate_password`) |
| Email | validado y normalizado (minúsculas; gmail sin puntos en local) |
| `email_verified` | **false** hasta verificar |
| Verificación | **requerida**: `POST /auth/verify-email` con token; en prod el token va por email; en dev se devuelve en la respuesta |
| Auto-login | **NO**: el registro devuelve `user_id`/mensaje, **no tokens**; hay que hacer **login** después |
| Rate limit | por IP (`register_per_minute`) |

---

# 4. Decisión congelada — Registro

- osap-api expone un **proxy público** `POST /api/v1/auth/register` que reenvía a osap-auth
  (sin service client, sin BD).
- El Web muestra un **formulario de registro** (email, password, name) → `POST /api/v1/auth/
  register`.
- Tras registrar (éxito o email existente, ambos 200 genérico):
  - El Web muestra "**verifica tu email**" (no inicia sesión).
  - En **dev**, si llega `verification_token`, el Web puede autoverificar o mostrar el paso de
    verificación.
- Después de verificar, el flujo continúa con **Login** (osap-auth → tokens).

## Registro (no autenticado) → Verificación → Login

```
NO autenticado
   ├── Registro → osap-auth → usuario (email_verified=false)
   ├── Verificación → osap-auth → email_verified=true
   └── Login → osap-auth → tokens
```

---

# 5. Fuera de v1

- CRUD/roles/tier en el Web.
- Segundo sistema de credenciales.
- Tabla de usuarios en osap-api.
- Registro que escriba en storage.

---

# 6. No implementar todavía

- No se implementa el registro aún.
- No se toca lo ya cerrado (login, voto, compositores, valoración, administración).

---

*Decisión de Registro v1 (2026-08) — aprobada; no implementado.*



## Parte: registro-v1-contract.md

---

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



## Parte: implementation-prompt-web-registro-v1.md

---

# Web OSAP — Prompt de implementación: Registro de usuario (v1)

**Estado:** PROMPT DE IMPLEMENTACIÓN. **Alcance:** registro + verificación de usuario.
**Base:** `docs/registro-v1-decision.md`, `docs/registro-v1-contract.md`.
**Sin auto-login, sin service client, sin BD de usuarios en osap-api.**

---

## Rol

Ingeniero sobre osap-api (backend) y el Web OSAP (`web/`). Implementa el registro conforme al
contrato. osap-api actúa como **proxy público** hacia osap-auth; osap-auth es la autoridad de
identidad.

---

## Alcance

- Registro de usuario (Web → osap-api → osap-auth).
- Verificación de email.
- **No**: auto-login, service client, tabla de usuarios en osap-api, roles/tier en el Web,
  segundo sistema de credenciales.

---

## 1. Backend — proxy de registro/verificación

- Añadir config `osap_auth_base_url` (URL base de osap-auth para llamadas de usuario, p. ej.
  `http://127.0.0.1:8200` en dev, o la URL de osap-auth en prod).
- Crear `AuthProxyClient` (sin service token — es una operación de identidad pública):
  - `register(email, password, name)` → `POST {base}/auth/register`.
  - `verifyEmail(token)` → `POST {base}/auth/verify-email`.
- Rutas **públicas** de osap-api (relay):
  - `POST /api/v1/auth/register` → relay a osap-auth; response genérica (200), **no** revelar si
    el email existía.
  - `POST /api/v1/auth/verify-email` → relay `{token}` → `{message: "email verificado"}`.
- Errores: **422** (email/password/payload), **429** (rate limit), **5xx** → 502/503 (osap-auth
  caído). Email existente **no** es error (200 genérico).

## 2. Frontend — AuthClient

- `AuthClient.register(email, password, name)` → `POST /api/v1/auth/register`.
- `AuthClient.verifyEmail(token)` → `POST /api/v1/auth/verify-email`.
- Sin auto-login: el registro devuelve `user_id`/mensaje, **no** tokens.

## 3. Frontend — formulario y flujo

- `RegisterForm` (email, password, name) → `register()`.
- Tras enviar (éxito o ya existía, ambos 200 genérico): mostrar **"verifica tu email"**.
- En dev, si `verification_token` llega en la respuesta, autoverificar
  (`verifyEmail(token)`) o mostrar el paso de verificación.
- Acceso desde el header: enlace **"Registrarse"** junto a Login (solo cuando no hay sesión).
- Después de verificar, el usuario hace **Login** (no se inicia sesión automáticamente).

## 4. i18n

- Claves de registro/verificación en 5 idiomas: registro.titulo, registro.email,
  registro.password, registro.name, registro.submit, registro.verifyEmail,
  registro.checkYourEmail, registro.alreadyExists (genérico, no revelar).

---

## 5. Tests

- **Backend**: `AuthProxyClient.register/verifyEmail` hacen las llamadas correctas a osap-auth
  (fake HTTP); rutas `POST /api/v1/auth/register` y `/verify-email` relay (200/422/429/5xx);
  anti-enumeración (email existente → 200 genérico, no 409).
- **Frontend**: `AuthClient.register/verifyEmail` (fetch mockeado); `RegisterForm` éxito →
  "verifica tu email"; email existente → mismo genérico; 422 → validación; **no auto-login**.

---

## 6. NO hacer

- No crear tabla de usuarios en osap-api.
- No usar service client para registro.
- No escribir en storage.
- No añadir roles/tier en el Web.
- No tocar lo ya cerrado (login, voto, compositores, valoración, administración).

---

## 7. Validación

- Backend: `ruff`, `mypy`, `pytest` limpios.
- Frontend: `tsc --noEmit`, `vitest run`, `vite build`.

---

*Prompt de implementación de Registro v1 (2026-08) — no implementado.*



