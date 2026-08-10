# Web OSAP — Prompt de implementación: cuenta, login, logout y renovación de sesión (v1)

**Estado:** PROMPT DE IMPLEMENTACIÓN (preparación). **Alcance limitado:** solo cuenta de
usuario / Login / Logout / renovación de sesión. **No** se toca voto, compositores ni
administración en este prompt (se conectarán después sobre esta base).

---

## Rol

Ingeniero de frontend sobre el Web OSAP (`osap-api/web`). Implementa el login real contra
osap-auth y la gestión de sesión, conforme a:

- decisión: `_docs/account-login-v1-decision.md`;
- contrato: `_docs/account-login-v1-contract.md`.

---

## Alcance

Solo:

- login (email+password);
- acceso a `access_token` / `refresh_token`;
- renovación de sesión (refresh, rotación, retry único);
- logout y limpieza de sesión.

**Fuera de alcance:** voto, compositores, administración, `tier`.

---

## Estado actual (frontend)

- `web/src/state/auth.ts` — Zustand con `token`, `user`, `login(token)`, `logout()`, `isAdmin()`.
  Hoy el login es un **placeholder** (pega un JWT por `window.prompt`). Se sustituye por el
  login real (email+password → `/auth/login`).
- `web/src/api/ApiClient.ts` — ya soporta `setToken`/`getToken` y adjunta
  `Authorization: Bearer`. **No** tiene manejo de 401 (refresh+retry).
- `web/src/layouts/Layout.tsx` — header con botón Login/Logout (placeholder). Se conserva la
  navegación, se conecta al login real.

---

## Prerrequisitos de integración

- El Web llama a los endpoints de osap-auth (`POST /auth/login`, `POST /auth/refresh`).
- osap-auth debe permitir el origen del Web (CORS) o servirse a través de un proxy inverso que
  exponga `/auth/*`. Confirmar la URL base de osap-auth en el entorno.

---

## 1. Auth store (Zustand) — sesión real

`web/src/state/auth.ts`:

- Estado: `accessToken`, `refreshToken`, `user` (`{user_id, roles, email_verified}`), `status`
  (`"anonymous" | "authenticated" | "refreshing"`).
- `login(email, password)`: llama `POST /auth/login` → guarda access en memoria y refresh en
  `localStorage`; actualiza `user`.
- `logout()`: borra el refresh de `localStorage` y limpia el estado local.
- `refreshSession()`: usa el **refresh vigente** (`POST /auth/refresh`) → guarda el **nuevo**
  access y el **nuevo** refresh (rotación). Si falla → `logout()`.
- `rehydrate()`: al arrancar, si hay refresh en `localStorage`, recupera la sesión
  (refresco proactivo). El access NO se persiste (solo memoria).
- `isAdmin()` y `isAuthenticated()` son **solo presentación** (ver §5).

## 2. Login form/page

- Un formulario **email + password** que llama a `login()`.
- Estados: cargando, error (401 credenciales inválidas → mensaje), éxito (redirige / refresca la
  navegación).
- Reemplaza el `window.prompt` actual.

## 3. ApiClient — acceso con 401 + retry único

`web/src/api/ApiClient.ts`:

- Adjunta `Authorization: Bearer <accessToken>` cuando hay sesión.
- **Manejo de 401:** si una petición devuelve 401:
  1. pide al auth store que haga `refreshSession()` (si no está ya refrescando);
  2. repite la **misma petición una sola vez** con el nuevo access;
  3. si vuelve a 401 → `logout()`.
- **Evitar bucles infinitos:** el refresh/retry se hace como máximo una vez por petición; nunca
  en cascada.
- Rotación: tras el refresh se usa **siempre el último `refresh_token`** (nunca uno obsoleto).

## 4. Renovación proactiva

- El Web puede leer `exp` del access token (decodificación **solo para presentación/UI**) y
  refrescar antes del vencimiento (TTL 15 min) con un timer, o bien refrescar únicamente en el
  401. Recomendado: refresco proactivo + retry en 401 como respaldo.

## 5. Presentación vs seguridad

> **El frontend puede decodificar el JWT únicamente para estado de presentación. Nunca debe
> tratar un claim decodificado localmente como prueba de autenticación o autorización.**

- `roles.includes("admin")` en el frontend es **solo UI** (ocultar/mostrar); nunca una decisión
  de seguridad.
- No se inventa `tier`.

## 6. Navegación

- Header: **Login** cuando `status === "anonymous"`; **Logout** (+ badge de usuario) cuando hay
  sesión. Reutiliza la estructura actual de `Layout.tsx`.

## 7. i18n

- Claves nuevas de login/logout/errores en los 5 idiomas (en/es/ca/fr/de), coherentes con
  `translations.ts`.

---

## Tests (obligatorios)

ApiClient es testeable vía stub de `globalThis.fetch` (sin red real).

### T1 — Flujo de extremo a extremo (login → recarga → refresh → 401 → retry → OK)

```
Login (email+password)
  ↓
access + refresh
  ↓
recarga del navegador (rehydrate desde localStorage)
  ↓
refresh (renovación proactiva o en 401)
  ↓
nuevo access + nuevo refresh
  ↓
petición a osap-api
  ↓
401 (access caducado)
  ↓
refresh automático
  ↓
retry único
  ↓
OK
```

### T2 — Refresh antiguo reutilizado → logout

```
refresh antiguo reutilizado
  ↓
401 ({"detail":"refresh reutilizado; sesiones revocadas"})
  ↓
logout
  ↓
limpieza de sesión (refresh eliminado de localStorage + estado local)
```

### Otros
- Login 200 → `access` en memoria, `refresh` en `localStorage`, `user` poblado.
- Login 401 (credenciales inválidas) → error mostrado, sin sesión.
- Login 422 (payload inválido) → validación.
- Logout → refresh eliminado + estado local limpio.
- El retry tras 401 se hace **una sola vez** (sin bucle).

---

## NO hacer en este prompt

- No tocar voto, compositores ni administración.
- No añadir `tier`.
- No tratar claims decodificados como seguridad.
- No crear un sistema de sesión paralelo a osap-auth.

---

## Validación

- `tsc --noEmit` limpio.
- `vitest run` (incluye T1 y T2).
- `vite build` OK.
- Confirmar que el comportamiento público existente (búsqueda, catálogo, etc.) no cambia.

---

*Prompt de implementación del Web OSAP v1 (2026-08) — cuenta/login/logout/renovación. No implementado.*
