# OSAP — login-v1 (consolidado)


## Parte: implementation-prompt-web-login-v1.md

---

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



## Parte: account-login-v1-decision.md

---

# OSAP — Login del Web OSAP con osap-auth (decisión v1)

**Estado:** DECISIÓN ARQUITECTÓNICA (a congelar). **No implementado.**
**Objeto:** cerrar el **mecanismo de login** real del Web OSAP (frontend) contra osap-auth.
Este documento fija la decisión; el contrato, los casos de autorización, el flujo, los tests y
el prompt de implementación se preparan en pasos posteriores.

---

# 1. Objetivo

Decidir cómo el Web OSAP inicia sesión con osap-auth y obtiene/maneja los tokens, de forma que
osap-api pueda resolver el `UserPrincipal` y autorizar, y que el frontend **no** decida permisos
ni invente `tier`.

---

# 2. Hechos de los contratos actuales

- osap-auth expone:
  - `POST /auth/login` (`{email, password}`) → `{access_token, refresh_token, user_id, roles, email_verified}`.
  - `POST /auth/refresh` (`{refresh_token}`) → nuevos tokens (rotación).
  - No expone `authorize` / `authorization_code` / PKCE / OIDC redirect hoy.
  - No emite `Set-Cookie`/httpOnly en el login (los tokens van en el body).
- Access token: JWT, TTL 900 s (15 min). Refresh token: TTL 30 días, rotación.
- Claims del user token: `token_use="user"` (discriminador canónico; `typ` por
  retrocompatibilidad), `sub=user_id`, `roles=[...]`, `email_verified`, `scope="openid profile api:vote"`.
- osap-api resuelve el `Principal` por `token_use` (user → `UserPrincipal`; fallback legacy de
  transición) y autoriza.

---

# 3. Decisión congelada — mecanismo de login

## 3.1 Flujo

```
Web OSAP ──(POST /auth/login, email+password)──► osap-auth
              ◄── { access_token, refresh_token, user_id, roles, email_verified }

Web OSAP ──(Authorization: Bearer access_token)──► osap-api
              └── resolve UserPrincipal (token_use=user, sub, roles, email_verified)
              └── autoriza según UserPrincipal / roles
```

## 3.2 Grant type

- **Directo (resource-owner-password)**: `POST /auth/login` con email+password.
- **No** se usa OIDC/`authorization_code`/PKCE en esta fase (osap-auth no lo expone). Se
  revisará cuando osap-auth lo soporte.

## 3.3 Almacenamiento del access token

- **En memoria** (estado de la app, p. ej. Zustand) durante la sesión.
- Se envía como `Authorization: Bearer <access_token>` a osap-api.
- No se persiste en `localStorage`/`sessionStorage` (reduce superficie de XSS).

## 3.4 Almacenamiento del refresh token

- **En `localStorage`** (persiste tras recarga) para poder renovar la sesión.
- **Trade-off aceptado:** riesgo XSS mitigado por prácticas de frontend (escapado, CSP).
  Alternativa más segura (refresh en httpOnly cookie vía proxy) se **difiere** a una decisión
  posterior si se necesita.
- Con **rotación**: cada `/auth/refresh` revoca el refresh anterior y emite uno nuevo.

## 3.5 Renovación

- Antes del vencimiento del access token (15 min) o al recibir **401**, el Web llama
  `POST /auth/refresh` con el `refresh_token` → obtiene un access + refresh nuevos.
- El Web renueva de forma **proactiva** (timer por `exp`) y/o en el primer 401 → re-intenta.
- Si el refresh falla (token revocado/vencido), se cierra sesión (logout).

## 3.6 Claims usados por el frontend (solo UI)

El frontend decodifica (sin verificar firma) `token_use`, `sub`, `roles`, `email_verified`
para la **UI** (mostrar Login/Logout, ocultar/mostrar acciones). **No** es el mecanismo de
seguridad.

- **No** decide que un usuario es admin: solo oculta/muestra; osap-api aplica `role=admin`.
- **No** inventa `tier`: el frontend no usa tier.

---

# 4. Frontera de seguridad

- La seguridad real está en **osap-api** (resuelve `UserPrincipal`, valida roles/email_verified,
  y delega a storage con identidad de servicio).
- El frontend es solo presentación: oculta/muestra según `roles` (UI), nunca autoriza.

---

# 5. Cuestiones para el contrato (paso siguiente)

1. Confirmar el shape de `LoginResponse` / `RefreshRequest` y los códigos de error de
   `/auth/login` y `/auth/refresh` (400/401/422).
2. Confirmar la **rotación** del refresh token (revocación del anterior).
3. Confirmar el manejo de **401** del access token expirado (response osap-api) para disparar el
   refresh.
4. Confirmar si osap-auth expondrá alguna cabecera `expires_in`/`exp` utilizable por el Web.

---

# 6. No implementar

- No se implementa todavía.
- No se añade OIDC/PKCE ni httpOnly-cookie en esta fase.
- No se crea un sistema de sesión paralelo en osap-api ni en el Web.

---

*Decisión de login del Web OSAP v1 (2026-08) — pendiente de aprobación; no implementado.*



## Parte: account-login-v1-contract.md

---

# OSAP — Contrato de Login/Refresh del Web OSAP (v1)

**Estado:** CONTRATO (congelado). **No implementado.**
**Base:** decisión `_docs/account-login-v1-decision.md`.
**Verificado** contra osap-auth real (127.0.0.1:8200).

---

# 1. Login — `POST /auth/login`

**Request:**
```json
{ "email": "usuario@example.com", "password": "..." }
```

**Respuesta 200 (éxito):**
```json
{
  "access_token": "<JWT user, ~775 chars>",
  "refresh_token": "<64 chars>",
  "user_id": "<uuid>",
  "roles": ["user"],
  "email_verified": true
}
```

| Código | Significado | Body |
|---|---|---|
| 200 | Login correcto | shape anterior |
| 401 | Credenciales inválidas | `{"detail": "credenciales inválidas"}` |
| 422 | Payload inválido (falta email/password) | `{"detail":[{type,loc,msg,input}]}` |

**Errores:** 401 y 422 (sin código de negocio adicional en el contrato de login).

---

# 2. Refresh — `POST /auth/refresh`

**Request:**
```json
{ "refresh_token": "<refresh>" }
```

**Respuesta 200:**
```json
{
  "access_token": "<nuevo JWT>",
  "refresh_token": "<nuevo refresh>",
  "user_id": "<uuid>",
  "roles": ["user"],
  "email_verified": true
}
```

## Rotación (obligatoria)
- Cada refresh emite un **nuevo `refresh_token`**; el refresh anterior queda **consumido**.
- **Reutilizar un refresh ya consumido** → `401 {"detail": "refresh reutilizado; sesiones revocadas"}`
  y **revoca toda la familia de sesiones** (los tokens posteriores de esa sesión dejan de servir).

## Errores
| Código | Significado | Body |
|---|---|---|
| 200 | Nuevos tokens (rotación) | shape anterior |
| 401 | Refresh inválido / reutilizado / sesión revocada | `{"detail": "refresh token inválido"}` o `{"detail": "refresh reutilizado; sesiones revocadas"}` |

> **Importante para el Web:** un solo refresh debe usar **siempre el `refresh_token` vigente**.
> Usar uno obsoleto revoca la sesión completa. No hay reintentos con refresh obsoletos.

---

# 3. Expiración del access token

- osap-api devuelve **401** cuando el access token falta/expirado/revocado.
- El Web, ante un **401** de osap-api:
  1. intenta **refresh** (`POST /auth/refresh` con el refresh vigente);
  2. si el refresh ok → repite la **petición original una sola vez**;
  3. si vuelve a **401** → **logout** (cierra sesión).
- **Evitar bucles infinitos:** el retry del refresh se hace una única vez por petición; nunca
  en cascada.

---

# 4. Persistencia de tokens

| Token | Dónde | Notas |
|---|---|---|
| Access token | **Memoria** (Zustand) | Se envía como `Authorization: Bearer <token>` a osap-api. No se persiste. |
| Refresh token | **`localStorage`** | Persiste tras recarga; rotación en cada refresh. |
| Logout | — | Elimina el `refresh_token` de `localStorage` y limpia el estado de sesión local. |

---

# 5. Precisión de presentación (no seguridad)

> **El frontend puede decodificar el JWT únicamente para estado de presentación. Nunca debe
> tratar un claim decodificado localmente como prueba de autenticación o autorización.**

- El frontend decodifica `token_use`, `sub`, `roles`, `email_verified` solo para **mostrar/
  ocultar** UI (Login/Logout, acciones admin).
- **Nunca** `roles.includes("admin")` en el frontend debe convertirse en una **decisión de
  seguridad**. La autorización la aplica **osap-api** (resuelve `UserPrincipal`, roles,
  email_verified).
- El frontend **no** inventa `tier`.

---

# 6. Frontera autenticación / autorización

```
              AUTENTICACIÓN
Web ──────────────────────────► osap-auth
      email + password
Web ◄──────────────────────────
      access + refresh

              AUTORIZACIÓN
Web ─── access token ──────────► osap-api
                                  │
                                  ├─ valida JWT (JWKS)
                                  ├─ UserPrincipal (token_use=user, sub, roles, email_verified)
                                  ├─ autoriza por roles
                                  └─ delega a storage con identidad SERVICE

```

**Nunca:**
- Web → osap-storage.
- Web → storage con token de usuario.
- Web → "soy admin" → osap-api (la UI no decide admin).

---

# 7. Incertidumbres resueltas

| §5 anterior | Resolución (contrato) |
|---|---|
| Shape Login/Refresh + errores | 200 `{access,refresh,user_id,roles,email_verified}`; 401 credenciales inválidas; 422 payload. |
| Rotación del refresh | Obligatoria; reutilizar refresh consumido → 401 + revoca familia de sesiones. |
| Manejo 401 (access expirado) | Web: refresh → repetir una vez → si 401 de nuevo, logout. Sin bucles. |
| `expires_in`/`exp` para el Web | El Web decodifica `exp` del access token (presentación) para refrescar proactivamente. |

---

*Contrato de Login/Refresh del Web OSAP v1 (2026-08) — congelado; no implementado.*



