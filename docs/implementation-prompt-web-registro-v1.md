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
