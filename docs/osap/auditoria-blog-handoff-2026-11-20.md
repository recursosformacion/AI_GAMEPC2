# Auditoría de seguridad e integración — Handoff OSAP → Blog (2026-11-20)

Estado: **auditoría de solo lectura**. No se ha modificado código, datos persistentes, Cloudflare,
`osap-auth`, `osap-storage` ni Chorus. No hay commits, tags ni despliegues.

Alcance auditado:

| Repo                                      | Referencia                                                                       | Estado local         |
| ----------------------------------------- | -------------------------------------------------------------------------------- | -------------------- |
| `recursosformacion/AI_GAMEPC2` (osap-api) | `origin/main` `88f769a` + PR #2 `origin/fix/blog-post-session-handoff` `c9929d2` | `main`, árbol limpio |
| `recursosformacion/osap-blog`             | `origin/main` `bcbf8e5` + PR #1 `origin/fix/editor-session-security` `8fa77e8`   | `main`, árbol limpio |

Los dos PR son **un único cambio contractual** (`POST /auth/session`) y hoy **no cumplen el
contrato en su totalidad**: no son desplegables ni conjuntamente (el PR #2 no compila y deja un
camino que rompe el login al blog; ver H-01/H-02).

Clasificación: **CRÍTICO** = seguridad / pérdida de datos / exposición; **ALTO** = funcionalidad
rota o incompatibilidad importante; **MEDIO** = defecto funcional o técnico limitado; **BAJO** =
deuda técnica o mejora.

---

## 1. Estado real de Git y diferencias con GitHub

```
osap-api   main @ 88f769a (up to date with origin/main, working tree clean)
           origin/fix/blog-post-session-handoff @ c9929d2  (2 commits sobre main)
osap-blog  main @ bcbf8e5 (up to date with origin/main, working tree clean)
           origin/fix/editor-session-security @ 8fa77e8  (5 commits sobre main)
```

Cambios del PR #2 (osap-api), `git diff 88f769a...c9929d2`:

| Archivo                      | Cambio                                                                                                                                                          |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `web/src/lib/blog.ts`        | `blogSessionUrl()` pasa a devolver solo `https://blog…/auth/session` (sin parámetros)                                                                           |
| `web/src/layouts/Layout.tsx` | `SidebarSection`: `sessionHandoff` deja de construir URL con tokens; nuevo `handleBlogHandoff` que crea un `<form method="POST">` oculto y hace `form.submit()` |

Cambios del PR #1 (osap-blog), `git diff bcbf8e5...8fa77e8`:

| Archivo             | Cambio                                                                                                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app.py`            | `GET /auth/session` → `POST /auth/session` con `Form(...)`; `next` restringido a ruta relativa; `can_edit` falla cerrado con `EDITOR_ROLES` vacío; `session_user` revalida contra `/auth/me` en cada petición |
| `tests/test_app.py` | 5 tests nuevos (allow-list vacía, roles, revalidación, token revocado, POST-only)                                                                                                                             |
| `README.md`         | Documenta el POST y el fallo cerrado                                                                                                                                                                          |

---

## 2. Revisión de los dos PR

| #   | Requisito                                             | Resultado                                                                                                                                                                      | Evidencia                                                             |
| --- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| 1   | OSAP envía `access_token`/`refresh_token` por POST    | **Parcial**: el sidebar sí; el retorno del login OIDC **no** (H-05)                                                                                                            | `Layout.tsx:298-327` vs `Layout.tsx:463`                              |
| 2   | El formulario apunta al endpoint correcto             | **Sí** (`${blogBaseUrl()}/auth/session`)                                                                                                                                       | bundle `ga(){return blog…/auth/session}`                              |
| 3   | Sin credenciales en URL, historial ni Referer         | **No** en el camino de retorno OIDC: `window.location.assign(blogSessionUrl(token, rt, "/admin"))` **no compila** (H-01); la versión publicada sí envía tokens en query (H-02) | `tsc` TS2554 en `Layout.tsx:464`                                      |
| 4   | `next` sin redirección externa                        | **Sí** en el PR #1 (`next.startswith("/") and not next.startswith("//")`)                                                                                                      | `app.py:878`; comprobado con `https://evil.example`, `//evil.example` |
| 5   | El blog acepta POST y rechaza el GET con credenciales | **Sí** (`GET /auth/session?token=…` → **405**)                                                                                                                                 | `var/audit_blog_handoff.py` (12/12)                                   |
| 6   | Errores de autenticación sin sesión parcial           | **Sí**: token inválido → `303 /?session=error` **sin** `Set-Cookie`                                                                                                            | idem                                                                  |
| 7   | Logout y renovación siguen funcionando                | **Sí** (`GET /logout` borra las 3 cookies; `refresh_tokens` rotación con caché de 60 s)                                                                                        | idem + `app.py:396-424`, `app.py:573-606`                             |
| 8   | Compatible con dev y producción                       | **Riesgo**: open redirect preexistente solo en producción (H-03); `next` del OSAP apunta a `/admin` y producción usa `/p` (H-04)                                               | `app.py:922-936`, `system.py:92-104`                                  |

Conclusión: la parte del blog (PR #1) es correcta y verificable. La parte del cliente (PR #2)
cumple en el sidebar, pero **rompe el type-check y deja el principal camino de entrada
(login → volver al blog) enviando el token en la URL**.

---

## 3. Pruebas ejecutadas y resultados exactos

Entorno: Windows, PowerShell 5.1, MariaDB **10.4.32** (`127.0.0.1:3306`), sin SQLite.
Logs en `var/` (sin versionar).

### 3.1 OSAP API (backend)

| Comando                                                                                               | Resultado                                                                                                                                       |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `python -m pytest tests/osap -q` (con `OSAP_DATABASE_URL` al MariaDB local)                           | **946 passed, 2 skipped**, 396 s, exit 0                                                                                                        |
| `python -m pytest tests/osap/test_amigos.py -q`                                                       | **69 passed**, 33 s                                                                                                                             |
| `python -m pytest tests/osap -q -k "auth or token or workspace or session or jwt or jwks or service"` | **125 passed**, 56 s                                                                                                                            |
| `python -m ruff check src/osap tests/osap`                                                            | **1 error** `I001` import block sin ordenar en `src/osap/api/contracts/__init__.py:6` (preexistente, `d2236a5`)                                 |
| `python -m mypy src/osap`                                                                             | **2 errores preexistentes** (`application/amigos.py:413` `no-any-return`, `api/platform/amigos.py:532` `return-value`; último cambio `067d4cb`) |

### 3.2 OSAP frontend (`web/`)

| Comando                                  | Resultado                                                                                                                                                                   |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tsc --noEmit` (main)                    | **exit 0**                                                                                                                                                                  |
| `tsc --noEmit` en worktree del PR #2     | **exit 2** → `src/layouts/Layout.tsx(464,22): error TS2554: Expected 0 arguments, but got 3`                                                                                |
| `vite build` en el worktree del PR #2    | **exit 0** (197 módulos, `✓ built in 23.72s`) — Vite no ejecuta type-check; el bundle generado no contiene `auth/session?` ni `refresh_token=`                              |
| `vitest run src/App.navigation.test.tsx` | **7 de 8 fallan** (`Unable to find role="heading" …`, `OpenMusicRepository`, `Classification`), 86 s — se reproduce igual sobre `main` ⇒ preexistente, no causado por el PR |
| `vitest run` (suite completa)            | **Inconclusa**: el runner se bloquea (0 % CPU, >15 min) tras `src/Sources.test.tsx`; se conserva el log parcial en `var/vitest_audit2.log`                                  |

Nota de entorno: `http://osap-blog/` responde **503** (uvicorn 8500 no está levantado); el
“rebuild de `web/dist`” deja de refrescarse porque el/los procesos `vite build --watch` están
caídos (el bundle servido sigue siendo el de `main`, ver H-02). `http://osap-app` y
`/api/v1/system/health` responden 200.

### 3.3 Pruebas de integración del handoff (entorno aislado)

`var/audit_blog_handoff.py` carga la app del **PR #1** con `TestClient` (sin red ni BD; `public_user`
sustituido) exportando antes la revisión con `git archive` (no toca el working tree del blog).
Resultado: **12/12 comprobaciones OK**

```text
[PASS] POST /auth/session valido -> 303 /admin
[PASS] cookies HttpOnly emitidas (access/refresh/session)
[PASS] GET /auth/session?token=... -> 405
[PASS] rutas /auth/session solo POST
[PASS] token invalido -> 303 /?session=error sin cookies
[PASS] sin token -> 303 /login
[PASS] next='https://evil.example/' -> /admin (no externo)
[PASS] next='//evil.example/' -> /admin (no externo)
[PASS] next='https://evil.example' -> /admin (no externo)
[PASS] can_edit con allow-list vacia -> False
[PASS] GET /logout borra las 3 cookies
[PASS] GET /logout next externo -> /
```

Blog: `python -m pytest tests -q` en `osap-blog` (rama del PR #1) → **18 passed**, 6.2 s.

Pruebas **no** ejecutadas y motivo: e2e en navegador OSAP→blog (el blog en dev está caído, 503);
auditoría de entorno prod (prohibido tocar producción); `vitest` completo (se bloquea);
`asyncio` de endpoints (handler síncrono verificable solo por inspección).

---

## 4. Errores encontrados y gravedad

### H-01 · ALTO · El PR #2 no compila (`tsc`)

- **Causa**: `blogSessionUrl()` pasó de `(token, refreshToken, next)` a `()` pero quedó una llamada
  con 3 argumentos: `web/src/layouts/Layout.tsx:463-465` (`handoffToBlog`).
- **Reproducción**: `git worktree add … origin/fix/blog-post-session-handoff` + `tsc --noEmit`
  → `TS2554` (exit 2). `npm run build` (= `tsc --noEmit && vite build`) fallaría; `vite build`
  directo “pasa” porque no valida tipos.
- **Propuesta**: extraer un `submitBlogSession({accessToken, refreshToken, next})` compartido y
  usarlo tanto en `SidebarSection` como en `handoffToBlog` (POST + `form.submit()`).

### H-02 · ALTO · El camino de entrada desde el blog sigue llevando credenciales en la URL

- **Causa**: el bundle servido por Apache (`web/dist/assets/index-0Qs0paW1.js`, compilado el
  2026-11-20 12:53 desde `main`) usa `${blog}/auth/session?token=…&next=…&refresh_token=…`.
  Ese camino es el del retorno OIDC (`?auth=login&return_to=blog` → `handoffToBlog` →
  `window.location.assign(con query)`), no solo el sidebar.
- **Efecto actual**: si PR #1 entra en producción **antes** que el frontend nuevo, el blog
  (POST-only) responde **405** a este GET → el login desde el blog deja de funcionar (ver H-06).
- **Propuesta**: cerrar H-01 y desplegar el frontend en el **mismo** cambio que el blog.

### H-03 · CRÍTICO (solo producción) · Open redirect en `GET /logout`

- **Causa**: `app.py:928-931` permite `next` absoluto cuando su `netloc` está en
  `{netloc(OSAP_URL), netloc(PUBLIC_URL)}`. En **dev** ambos son hosts distintos
  (`http://osap-app` vs `http://osap-blog`); en **producción** ambos son el **mismo** host
  (`*.openmusicrepository.com`) y `urlparse(...).netloc` incluye puerto ⇒ **cualquier**
  `https://blog.openmusicrepository.com/<texto-de-atacante>` se acepta como destino.
- **Reproducción conceptual** (solo dev configura `OSAP_URL` interno): `GET /logout?next=https://blog.openmusicrepository.com/evil`
  ⇒ `303` a un destino arbitrario del mismo dominio (usado hoy por OSAP con
  `blogLogoutUrl(<origin>/SENDA)` → `/logout?next=https://app…/`), vector clásico de phishing.
- **Propuesta**: aceptar solo rutas relativas (`startswith("/")` y no `//`) y, si hace falta
  volver a OSAP, construir el destino con una allow-list exacta de `scheme://host[:puerto]`.

### H-04 · MEDIO · Rutas del panel editorial divergentes (`/admin` vs `/p`)

- **Causa**: OSAP pide `next="/admin"` (`Layout.tsx:312`) mientras `ads_web` en OSAP calcula
  `panel = "/p" if base.endswith("/publicidad") else "/admin"` (`src/osap/api/platform/system.py:98-104`).
- **Efecto**: en la variante `/publicidad` el editor aterriza en `/admin` (404/redirección), y
  además `ads_web` sigue generando `…auth/session?token=…` (GET) — incompatible con H-02.
- **Propuesta**: un único `blogAdminPath()` (configurable) usado por OSAP; migrar `ads_web` al
  POST igual que el sidebar.

### H-05 · MEDIO · Handoff asimétrico entre sidebar y retorno de login

- **Causa**: `SidebarSection` hace POST, `handoffToBlog` usa `window.location.assign`. Con
  `next` fijo por entrada en el sidebar (`/admin`) no se puede volver al artículo que el usuario
  abrió desde el blog.
- **Propuesta**: un solo helper de handoff que reciba `next` (ruta interna) y se use en ambos
  caminos; el `next` del sidebar deja de ser constante.

### H-06 · ALTO · Despliegue acoplado (contractual)

- El PR #1 rompe el contrato GET (`GET /auth/session` → 405). Un frontend antiguo —o el bundle
  de `main` en dev, H-02— **solo** sabe hacer GET con tokens. Blog nuevo + frontend viejo = login
  al blog caído. Debe desplegarse conjuntamente y **nunca** el blog por separado.

### H-07 · MEDIO · Ausencia de CSRF (login CSRF) y CSRF de logout

- `POST /auth/session` (sin token) acepta un `access_token` cualquiera: un tercero puede iniciar
  sesión en el navegador de la víctima con **su** cuenta (login CSRF) ⇒ sus comentarios/borradores
  se registran con la identidad del atacante. `GET /logout` es además CSRF por diseño (borra
  cookies sin token).
- **Propuesta (no bloqueante)**: cookie `osap_handoff` de un solo uso emitida por `GET /` y exigida
  en el POST; convertir logout en `POST` con token de formulario y/o `SameSite=Strict` para la
  cookie de sesión.

### H-08 · MEDIO · Dependencia no declarada con `python-multipart`

- `app.py` usa `Form(...)` desde la rama del PR #1. Hoy funciona (`requirements.txt` ya incluye
  `python-multipart` y está instalado en el venv del blog), pero un despliegue limpio sin ese
  paquete fallaría en el arranque con `RuntimeError: Form data requires "python-multipart"`.
- **Propuesta**: fijar la dependencia en el `requirements.txt` del blog y verificar en el venv de
  producción **antes** de desplegar (regla del AGENTS.md).

### H-09 · MEDIO · Endpoints `async` con cuerpo síncrono

- `src/osap/api/http/sessions.py:39` (`get_resolution_session`) y `:62` (`get_resolution_results`)
  son `async def` pero llaman a funciones síncronas de BD: bloquean el event loop.
- **Propuesta (no urgente)**: convertir a `def` (FastAPI los mueve al threadpool) o a
  `await run_in_threadpool(...)`.

### H-10 · MEDIO · Mismas credenciales de handoff en Chorus por URL

- `web/src/lib/chorus.ts:22-31` construye `https://chorus…/?token=<access>&refresh_token=<refresh>`;
  son **las mismas** credenciales que el PR protege para el blog. En desarrollo, además, el
  handoff de Chorus emite el token en query en la **portada** (`/?token=…`).
- **Propuesta**: replicar el patrón POST en Chorus cuando su PR correspondiente esté disponible
  (fuera del alcance de este cambio; no se ha tocado Chorus).

### H-11 · BAJO · Lint/tipos rojos preexistentes

- `ruff` (1 `I001`) y `mypy` (2 errores) fallan sobre `main` desde antes de estos PR. No son del
  cambio, pero impiden usar “verificación estándar limpia” como criterio de aceptación.

### H-12 · BAJO · `vitest` con suite bloqueada y `App.navigation` roja

- Preexistente en `main`; impide usar `vitest run` como puerta de despliegue hasta arreglarlo.

---

## 5. Integración con OSAP Auth (solo lectura de osap-api)

| Comprobación                          | Resultado                                                                                                                                                                |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Audiencia de tokens de servicio       | OK: `ClientCredentialsServiceTokenProvider(audience=None)` = `aud=osap-api` para storage; `aud=osap-support` explícito para support (`wiring.py:557,580`)                |
| `token_use` / `typ`                   | OK en el camino JWKS (`_principal_from_payload`); **fallback legacy** (`_resolve_legacy`) sigue aceptando tokens sin `token_use` y resuelve usuario por defecto          |
| Renovación / rotación de refresh      | OK en el frontend (single-flight + rotación, `auth.ts:193-229`); en el blog, caché de 60 s por refresh token y rotación persistida (`app.py:396-424,596-603`)            |
| Sesiones expiradas/revocadas          | OK tras PR #1: `session_user` revalida `/auth/me` en cada petición (antes la cookie firmada de 7 días conservaba roles)                                                  |
| Tokens en logs                        | OK: sin `console.log` de tokens en `web/src`; en backend solo se registra el tipo de error/HTTP                                                                          |
| Credenciales por URL                  | **Fallo** en blog (H-02/PR #2) y Chorus (H-10); **storage/admin, support y ads siguen con `?token=`** (ver §6)                                                           |
| Credenciales obsoletas en el frontend | Access en memoria, refresh en `localStorage`; `logout()` limpia ambos y el temporizador. Observación: al cerrar sesión se carga el blog con `?next=<origin>` (H-03/H-07) |

**No se ha modificado `osap-auth`.** No se detecta ningún defecto que obligue a tocarlo; el
único punto a revisar allí sería adelantar la eliminación del fallback legacy `token_use`.

---

## 6. Integración con OSAP Storage (solo lectura)

| Comprobación                                               | Resultado                                                                                                                                                                                                                                                                                                                      | Consumidores                                       |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------- |
| Registro de Files (`POST /api/v1/files` y `/files/upload`) | OSAP solo usa **`/api/v1/files/upload`** (`contribution_uploads.py:162-177`, scope `storage:write`)                                                                                                                                                                                                                            | `AmigosUpload`, aportaciones                       |
| Contrato antiguo vs V6 (`/composers` ↔ `/persons`)         | Puente explícito con fallback 400/404/405 (`_call`/`_call_persons_first`). **OSAP no consume ninguna ruta `/api/v6/*`** de storage (grep vacío en `src/osap`); storage ya las expone (`prefix="/api/v6"`, `api/routes/v6.py:37`) | Compositores, RISM, OMR |
| Uso de SHA-256                                             | Storage **deduplica por sha256** en upload; OSAP **no calcula ni verifica** sha256 al subir/bajar (no usa `/verify`)                                                                                                                                                                                                           | `amigos_upload`, aportaciones                      |
| Integridad vs identidad vs dedup                           | Dedup = sha256 (storage); identidad pública = `file_id`; OSAP sirve `/api/v1/amigos/media/{file_id}` **sin** comprobar `sha256`, `size_bytes` ni `mime_type` del registro                                                                                                                                                      | `platform/amigos.py:488-494`                       |
| Archivos borrados                                          | `delete_amigos_upload` **no existe**: un borrado en storage deja la fila en `amigos_uploads`, y lo contrario (fila huérfana) hace `404` público                                                                                                                                                                                | `amigos_uploads`                                   |
| Permisos de descarga                                       | Proxy interno con **token de servicio** (`fetch_file` → `storage:read`); descarga pública de `/api/v1/amigos/media/{id}` **sin autenticación**. Además el registro se ata a un `group_id` aunque el scope sea `events`/`blog` (`store_group=""`, `amigos_uploads.group_id NOT NULL`) ⇒ `record_upload` puede fallar en MariaDB | `platform/amigos.py:452-494`, `mysql.py:1647-1656` |
| Audiencias/scopes                                          | OK: `storage:read` para lectura, `storage:admin` para administración, `storage:write` para subidas                                                                                                                                                                                                                             | `wiring.py:288-292,383-409,506-530`                |

**No se ha modificado Storage.** Incompatibilidades documentadas: (a) falta de verificación de
sha256/size en el proxy de medios; (b) ausencia de borrado coordinado; (c) `group_id` obligatorio
para subidas de blog/eventos; (d) URLs de administración con `?token=` (siguiente punto).

### 6.1 Tokens de servicio en la URL (hallazgo transversal, ALTO)

| Lugar                                                            | URL generada                                          |
| ---------------------------------------------------------------- | ----------------------------------------------------- |
| `src/osap/api/platform/system.py:48-73`                          | `${storage}/admin…?token=<storage:admin>`             |
| `src/osap/api/platform/system.py:90`                             | `${support}/api/v1/admin/web/…?token=<support:admin>` |
| `src/osap/infrastructure/storage/storage_composer_client.py:384` | `${storage}/admin?token=<…>`                          |
| `src/osap/api/platform/system.py:101-103`                        | `ads/auth/session?token=<token de USUARIO>`           |

Son enlaces que abre el navegador del administrador: quedan en historial, Referer, logs de nginx
y en los `Referer` hacia terceros. La suite cubre el formato actual
(`tests/osap/test_storage_web.py`), así que un cambio de contrato aquí exige actualizar pruebas.

**Propuesta**: mismo patrón que el blog (POST de formulario o cookie de un solo uso), coordinado
con `osap-storage`/`osap-support`/`ai_publicidad`. Fuera del alcance de este PR; no se ha tocado.

---

## 7. Inventario de dependencias `amigos_*`

Productor del esquema: `osap_api` (MariaDB 10.4.32). `MysqlOpStore._init_amigos()`
(`src/osap/infrastructure/state/op/mysql.py:253-560`) crea **12** tablas en el **arranque**
(`CREATE TABLE IF NOT EXISTS` + `_ensure_column`): `amigos_groups`, `amigos_members`,
`amigos_articles`, `amigos_media`, `amigos_events`, `amigos_coral_details`,
`amigos_coral_attributes`, `amigos_group_links`, `amigos_uploads`, `amigos_actuaciones`,
`amigos_actuacion_groups`, `amigos_authorizations`. Verificado en `osap_api_test`:

```
amigos_actuaciones, amigos_actuacion_groups, amigos_articles, amigos_authorizations,
amigos_coral_attributes, amigos_coral_details, amigos_events, amigos_groups,
amigos_group_links, amigos_media, amigos_members, amigos_uploads
```

| Tabla                                                                                     | ¿Quién la usa hoy?                                                                                                  | Destino (arquitectura objetivo)                                                   |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `amigos_groups`                                                                           | Endpoints `/api/v1/amigos/groups*`, sitemap (`sitemap.py:185-190`), páginas SSR `/amigos/corales…`, 5 FKs entrantes | Chorus (grupos); OSAP solo necesita referencias externas                          |
| `amigos_members`                                                                          | `list_my_*`, permisos `/amigos/my/permissions`                                                                      | Chorus                                                                            |
| `amigos_articles`                                                                         | Blog general (`scope='general'`) + artículos de grupo; sitemap; `views_amigos`                                      | **General: OSAP**; grupo: Chorus/Blog                                             |
| `amigos_media`                                                                            | Medios de esos artículos (`replace_amigos_media`)                                                                   | Chorus/Blog                                                                       |
| `amigos_uploads`                                                                          | `POST /api/v1/amigos/uploads` + `GET /api/v1/amigos/media/{id}`                                                     | **Infraestructura de OSAP** (no exclusiva del blog)                               |
| `amigos_actuaciones`                                                                      | `AmigosEventsPage`, `/api/v1/amigos/events*`, `/admin/amigos/events`, sitemap (`sitemap_amigos_events`)             | **Sistema propio de anuncios de OSAP**                                            |
| `amigos_actuacion_groups`                                                                 | Participantes de una actuación (FK a `amigos_groups`)                                                               | Debe apuntar a una **referencia externa** de grupo (Chorus), no a `amigos_groups` |
| `amigos_authorizations`                                                                   | `list_amigos_authorizations`, admin de autorizaciones                                                               | Permisos editoriales de OSAP (se mantiene)                                        |
| `amigos_events`                                                                           | Auditoría de artículos (`add_amigos_event`), `list_events(group_id)`                                                | Auditoría (se mantiene; no es agenda)                                             |
| `amigos_coral_details` / `_attributes` / `amigos_group_links`                             | Ficha de coral y enlaces del grupo                                                                                  | Chorus                                                                            |
| `amigos_group_history` / `_catalog` / `_types` / `_section_templates` / `_role_templates` | Usadas por la API/UI que retira `chorus-separation.md`                                                              | Chorus (catálogo de secciones, plantillas)                                        |

Endpoints `amigos` activos: ~50 rutas en `src/osap/api/http/amigos.py` (grupos, artículos,
eventos, medios, `/my/*`, `/admin/amigos/*`, autorizaciones) y páginas SSR
`/amigos/articulos`, `/amigos/articulo/{id}[/{slug}]`, `/amigos/corales/*` (`src/osap/api/http/seo.py`).
Frontend: `AmigosGroupsPage`, `AmigosGroupDetailPage`, `AmigosEventsPage`, `AmigosBlogPage`,
`AmigosEditorPage`, `AmigosMyArticlesPage`, `AdminAmigos*` y las rutas `/amigos/*`
(`routes.tsx:99-112`). Sitemap: `_STATIC_PATHS` incluye `/amigos`, `/amigos/corales`,
`/amigos/eventos` y `/amigos/articulos`, y `sitemaps/amigos-1.xml` lista grupos y artículos.

**No es prescindible** ninguna tabla por el mero hecho de haberse migrado a Chorus: la decisión
pendiente es de contrato público (SEO/URLs) y requiere tabla de correspondencia + 301
(`AGENTS.md` y `docs/osap/chorus-separation.md:81`).

---

## 8. Incompatibilidades arquitectura actual ↔ objetivo

1. **Grupos**: OSAP sigue siendo dueño de `amigos_groups` y de 5 FK (incluida
   `amigos_actuacion_groups.group_id`), mientras `chorus-separation.md` declara Chorus como
   autoridad. Falta la **referencia externa** (`chorus_group_id`) para las actuaciones.
2. **Actuaciones**: hoy es una funcionalidad de OSAP acoplada a `amigos_groups`; la relación con
   grupos de Chorus debe ser **externa y opcional** (sin FK a la tabla antigua).
3. **`amigos_uploads`**: hoy asociada a `group_id` (`NOT NULL`) aun cuando el destino es
   blog/eventos. Es infraestructura compartida; debe desacoplarse del concepto de grupo
   (`owner_kind`/`owner_id` o `file_id` + metadatos).
4. **Blog**: artículo general de OSAP sigue en `amigos_articles` **y** hay un blog nuevo (`osap_blog`)
   con su propio modelo. Falta decidir la fuente de verdad y las 301 de `/amigos/articulo/...`.
5. **Storage**: contrato antiguo (`/composers`) y V6 conviven con fallback; OSAP aún no consume
   `/api/v6/*`; URL con `?token=` en administración.
6. **Auth**: fallback `token_use` legacy y tokens de usuario en URL (blog, ads, Chorus).

---

## 9. Correcciones recomendadas por prioridad

1. **(CRÍTICO)** `GET /logout`: aceptar solo `next` relativo (H-03). Un cambio de líneas en
   `osap-blog/app.py` + test.
2. **(ALTO)** Arreglar el PR #2 (H-01): un único `submitBlogSession()` usado por sidebar y
   `handoffToBlog`; añadir test que asegure que **ningún** camino construye URL con `token=`.
3. **(ALTO)** Desplegar blog + frontend **juntos** (H-06) y documentarlo en la entrega.
4. **(ALTO)** Migrar `ads_web` del `GET ?token=` al POST (H-04) o retirarlo hasta que el
   frontend nuevo esté desplegado.
5. **(MEDIO)** `python-multipart` fijado en el blog antes de desplegar (H-08).
6. **(MEDIO)** CSRF de `POST /auth/session` y de `GET /logout` (H-07).
7. **(MEDIO)** Verificación de sha256/size en `/api/v1/amigos/media/{id}` y borrado coordinado con
   storage (H-06 de §6).
8. **(MEDIO)** Endpoints `async` con BD síncrona (`sessions.py:39,62`).
9. **(BAJO)** Limpiar `ruff`/`mypy`/`vitest` para recuperar las puertas de calidad (H-11, H-12).
10. **(BAJO)** Planificar el POST también para storage/support/ads/Chorus (H-10 y §6.1).

---

## 10. Archivos concretos a modificar (si se autoriza)

| Prioridad | Repo      | Archivo                                                                                                                                              |
| --------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| CRÍTICO   | osap-blog | `app.py` (logout `next`), `tests/test_app.py`                                                                                                        |
| ALTO      | osap-api  | `web/src/lib/blog.ts`, `web/src/layouts/Layout.tsx`, tests de `lib/blog`                                                                             |
| ALTO      | osap-api  | `src/osap/api/platform/system.py` (`ads_web`, `storage_web`, `support_web`)                                                                          |
| ALTO      | osap-blog | `requirements.txt`, `README.md`                                                                                                                      |
| MEDIO     | osap-blog | `app.py` (CSRF), `templates/base.html`                                                                                                               |
| MEDIO     | osap-api  | `src/osap/api/platform/amigos.py`, `src/osap/application/amigos.py`, `src/osap/infrastructure/state/op/mysql.py`                                     |
| MEDIO     | osap-api  | `src/osap/api/http/sessions.py`                                                                                                                      |
| BAJO      | osap-api  | `src/osap/api/contracts/__init__.py`, `src/osap/application/amigos.py:413`, `src/osap/api/platform/amigos.py:532`, `web/src/App.navigation.test.tsx` |

---

## 11. Riesgos y pruebas necesarias antes de desplegar

Riesgos:

- **Login al blog caído** si los dos PR no viajan juntos (H-02/H-06).
- **Open redirect de producción** en `/logout` (H-03) — no reproducible en dev por configuración.
- **Regresión de `next`**: el editor debe aterrizar en `/admin` (o `/p`) tras el POST.
- Aterrizaje en `/login` si el token caduca entre el click y el POST (degradación aceptable).
- Los enlaces de mantenimiento con `?token=` siguen exponiendo tokens de servicio (§6.1).

Pruebas mínimas antes de desplegar:

1. `tsc --noEmit` y `vitest` verdes en `web/` con el PR #2 corregido (incluye nuevo test de
   “no hay `token=` en ninguna URL”).
2. `pytest tests/osap -q` verde (946+) y `pytest tests -q` en `osap-blog` (18+).
3. Prueba manual dev con Apache: login desde blog (`?auth=login&return_to=blog`) → vuelta a
   `/admin` por POST; URL sin `token=`; logout → OSAP sin sesión y blog sin cookies.
4. `GET /auth/session?token=…` → 405 y `POST` sin token → `/login`.
5. En producción (ventana autorizada): `curl -I 'https://blog…/logout?next=https://blog…/x'`
   debe responder `303` a `/` (valida H-03).
6. Comprobar `python-multipart` en el venv de producción del blog antes del restart
   (`…/.venv/bin/pip show python-multipart`).

---

## Anexo · Artefactos temporales de la auditoría (`var/`, no versionado)

| Script                                                   | Propósito                                                            |
| -------------------------------------------------------- | -------------------------------------------------------------------- |
| `var/audit_blog_handoff.py`                              | Simula el handoff contra el PR #1 (12 comprobaciones; `python var/audit_blog_handoff.py ..\osap-blog origin/fix/editor-session-security`) |
| `var/audit_db_schema.py`                                 | Solo lectura: versión MariaDB y tablas `amigos_*` en `osap_api_test` |
| `var/audit_dist.py`                                      | Comprueba si el bundle servido por Apache lleva tokens en la URL     |
| `var/audit_async_handlers.py` / `var/audit_async_ast.py` | Localizan handlers sync con cuerpo corrutina / métodos homónimos     |
| `var/*.log`                                              | Salidas de `pytest`, `vitest`, `tsc`, `mypy`, `rust` y `vite build`  |


## Primera revisión de Chorus — 22/11/2026

Esta revisión es estática y no modifica el repositorio de Chorus, que continúa en trabajo activo en `main`.

### Bloqueantes detectados

1. **Handoff con credenciales en query string (H-10 sigue abierto).** OSAP `web/src/lib/chorus.ts` construye `/?token=<access>&refresh_token=<refresh>`; lo usan `Layout.tsx` y `AmigosPage.tsx`. Chorus lo lee en `web/app.js` y limpia la URL después de cargar, pero el navegador y el servidor ya han recibido la URL completa. El refresh token puede permanecer hasta 30 días. El `referrerPolicy=no-referrer` reduce una vía de fuga, pero no evita historial ni access logs.
   
   Chorus ya dispone de `POST /api/v1/auth/handoff`: recibe los tokens en JSON, valida el access token con `osap-auth /auth/me` y establece cookies HttpOnly. OSAP todavía no utiliza ese endpoint. La corrección debe sustituir los enlaces con query por un POST con `credentials: include`, navegación posterior a la portada y CORS limitado al origen OSAP; Chorus debe validar también el origen en el endpoint.

2. **Claves foráneas incorrectas en la migración MySQL 006.** `migrations/mysql/006_group_articles_tables.sql` declara `author_user_id`, `publisher_user_id` y `reviewed_by` como referencias a `groups(id)`. Son identificadores de usuarios procedentes de osap-auth, no identificadores de grupos. En una instalación MySQL nueva estas restricciones pueden impedir crear o revisar artículos. La migración histórica 003 no tenía esas FKs; el arranque legacy puede saltarse 006, dejando un esquema distinto del de una instalación nueva.

3. **Verificación insuficiente del esquema de artículos.** `_safe_execute_migration` no compara las FKs esperadas de 006 y `_verify_final_schema` solo comprueba un mínimo numérico de FKs, no sus nombres ni tablas referenciadas. Por ello no detecta las referencias erróneas ni garantiza que una instalación legacy y una nueva tengan el mismo esquema. Hace falta una migración correctiva posterior a 006 y una verificación exacta de constraints.

### Riesgos y contradicciones adicionales

- Chorus aplica las migraciones MySQL 001 y 004–007 automáticamente durante el lifespan de la aplicación. No he ejecutado ninguna. La primera puesta en marcha en producción podría aplicar 006 automáticamente; no debe hacerse antes de corregirla y revisar el estado de la base de datos.
- `app/db.py` y `Settings.validate_database()` exigen `CHORUS_DATABASE_URL` MySQL/MariaDB; sin embargo, `docs/api-runtime.md` describe SQLite como runtime local. La rama SQLite de `initialise_database` no es alcanzable mediante el conector actual. README, runtime y configuración necesitan una única descripción coherente.
- El almacenamiento de ficheros de Chorus sigue siendo un directorio privado local (`CHORUS_STORAGE_ROOT`, por defecto `var/private`). No he encontrado en esta revisión una garantía de backup/restore de ese contenido. El propio README indica que el almacenamiento local es banco de pruebas, no persistencia de producción.
- El último commit de Chorus informa de 238/238 pruebas ejecutadas en MariaDB 10.4.32. No he podido confirmar un resultado de CI independiente ni que esas pruebas cubran una instalación MySQL nueva desde cero con 006.

**Conclusión provisional:** Chorus no debe incluirse todavía en el despliegue público de esta noche. Antes hay que corregir el handoff de tokens, arreglar las FKs de 006 con una migración posterior y acordar la persistencia/backup de ficheros. No he tocado el código de Chorus para no interferir con el trabajo activo de Ernie.
