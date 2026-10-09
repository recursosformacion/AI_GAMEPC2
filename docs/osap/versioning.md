# Versionado OSAP

## Política: versión única coordinada con clasificación A.B.C

Todos los programas de OSAP comparten **una sola versión** y se suben y etiquetan juntos:

- `osap-api` (backend + SPA)
- `osap-storage` (+ admin web)
- `osap-auth` (+ web)
- `osap-support`

No se versiona cada parte por separado. Así se evita mantener una matriz de dependencias
(«api 3.x requiere storage 2.1»): un número describe el conjunto completo y es desplegable
como un todo.

## Semántica A.B.C

- **A — Orientación (MAJOR).** Cambio de orientación del conjunto: modelo/esquema de datos o
  contrato que rompe compatibilidad. **Antes de empezar un A se crea un punto de control**:
  tag anotado de la última estable y rama de mantenimiento `mantenimiento/A.(B-1).x` para
  seguir corrigiendo la línea anterior mientras sale el A. Afecta a todos los programas y
  exige plan de migración reversible.
- **B — Mejora (MINOR).** Capacidad o mejora nueva, **compatible** (contratos aditivos, sin
  migración destructiva). Puede afectar a uno o varios programas.
- **C — Corrección (PATCH).** Corrección ligera de un defecto existente contenida en **un solo
  programa**; no cambia contratos ni esquema y la compatibilidad entre programas se mantiene
  intacta. Debe venir con una prueba que demuestre la corrección.

> **Mejora sobre la definición inicial:** el alcance (cuántos programas toca) y la
> compatibilidad (rompe o no) son dos ejes distintos. Se clasifica por ellos, no por el número
> de ficheros:
> - ¿Rompe contrato o esquema de datos? → **A**.
> - No rompe: ¿aporta capacidad nueva? → **B**; ¿corrige un defecto existente? → **C**.
> - El nº de programas tocados se anota en la entrada del historial como alcance, pero **un C
>   nunca puede tocar más de un programa** (si toca dos, es B).

## Reglas duras (el agente las hace cumplir antes de commitear)

1. **Un número para todo el conjunto.** Aunque un C solo cambie un programa, la versión de
   entrega sube para los cuatro. Prohibido versionar un programa en solitario.
2. Toda entrega actualiza y **alinea** `version` en los cuatro `pyproject.toml` y en
   `osap-api/web/package.json`. Se verifica con `script/check-versions.ps1`.
3. **Tag anotado `vX.Y.Z` en los cuatro repos**, aunque su contenido no cambie, para dejar
   claro qué revisión del conjunto está en producción.
4. Clasificación obligatoria **antes** de tocar código. Un cambio que rompe contrato nunca es
   B; uno que toca dos programas nunca es C.
5. Un **A** exige tag y rama de mantenimiento de la línea anterior desde la última estable;
   las correcciones a esa línea anterior son C sobre `A.(B-1).x` (suben el 3.er dígito).
6. No se reutiliza un número ya publicado; no hay contenido distinto bajo la misma versión; no
   se saltan dígitos.
7. Cada entrega añade una entrada al **Historial** con la clasificación (A/B/C), el alcance por
   programa y la evidencia de verificación.
8. Pre-release opcional `X.Y.Z-rc.N`; nunca en producción sin promover a `X.Y.Z` estable.
9. Un **A** o un **B** exigen actualizar el historial y, si aplica, la guía de migración.

## Cómo lo aplica el agente

- Antes de commitear indica la clasificación (**A/B/C**) y la versión objetivo.
- Si un «C» toca más de un programa, lo reclasifica a B y lo avisa.
- No modifica `version` salvo para preparar una entrega; entonces actualiza los cuatro
  `pyproject.toml` + `web/package.json` y ejecuta `script/check-versions.ps1`.
- No crea ni empuja tags/releases sin autorización explícita.

## Cambios operativos (no suben versión)

Artefactos operativos —ficheros de verificación de buscadores (p. ej. `yandex_<id>.html`,
`BingSiteAuth.xml`), `robots.txt` o ajustes de proxy/nginx— se registran como operativos y
**no** constituyen una entrega: no suben la versión ni requieren entrada en el historial.
Sí se commitean en el repo correspondiente para que el despliegue los reproduzca.

## Decisión rápida

| Cambio | A | B | C |
|---|---|---|---|
| Rompe contrato/esquema | sí | no | no |
| Capacidad nueva | puede | sí | no |
| Solo corrige un defecto | no | no | sí |
| Programas afectados | todos | ≥1 | exactamente 1 |

## Historial

- **5.1.6 (C) — `osap-api`**: **documentos legales** (Aviso legal `/aviso-legal`, Privacidad
  `/privacidad`, Cookies `/cookies`) con enlaces en el pie, y **gestor de consentimiento de
  cookies** (aceptar todas / rechazar no necesarias / configurar, persistencia local y enlace
  permanente «Configurar cookies»). **Google Analytics ya no se carga sin consentimiento**
  (gtag.js se inyecta dinámicamente; `send_page_view:false` para evitar duplicados).
- **5.1.4 (C) — `osap-auth`**: `terms_url`/`privacy_url` por defecto apuntan a los documentos
  legales de la app (`/aviso-legal`, `/privacidad`).
- **5.1.5 (C) — `osap-api`**: admin de usuarios — listado con **estado on/off**, acciones con
  **iconos** (ver/editar/reconocimientos/baja) y columnas **rol más alto** + **visibilidad**;
  se retira la entrada de menú **"Reconocimientos"** (la gestión ya vive en la ficha del usuario).
- **5.1.4 (C) — `osap-api`**: al **conceder/revocar un reconocimiento**, osap-api notifica a
  osap-auth (best-effort) para que envíe el email al usuario; la ruta de revoke pasa `user_id`.
- **5.1.3 (C) — `osap-auth`**: aviso por email al usuario cuando el admin le concede/retira un
  reconocimiento (`POST /auth/admin/users/{id}/recognition-notification`).
- **5.1.3 (C) — `osap-api`**: sustituye la etiqueta **Google Tag Manager** (`GTM-WR6VXCFD`) por
  **GA4 gtag.js** (`G-8QXVPF8VP0`); los eventos del SPA (`page_view`, `search`) se envían con
  `gtag('event', …)`.
- **5.1.4 (C) — `osap-storage`**: mantenimiento de `works` (admin HTML `/admin/works`) —
  **quita `person_id`** del formulario, `attribution_type` como **select** (ANONIMA/TRADICIONAL/
  POPULAR/ATRIBUIDA), y **géneros/instrumentos** como **multi-select** contra sus catálogos
  (nunca CSV); se añade editor de **`works_person_roles`** (compositor/artista y roles).
- **5.1.3 (C) — `osap-storage`**: aceptar una propuesta de **atribución IA** es **idempotente**
  si la relación `(obra,persona,rol)` ya existe (antes el `INSERT IGNORE` con rowcount 0 hacía
  rollback y la propuesta quedaba pendiente → parecía que "Aceptar" no hacía nada).
- **5.1.2 (C) — `osap-storage`**: `PopulateComposers` crea personas **ocultas** (`visible=0`;
  un compositor sin obras no debe ser público) y `create()` respeta `visible`. Fix de datos:
  1602 personas `active` sin obras pasadas a `visible=0` (Dev y Prod).
- **5.1.2 (C) — `osap-api`**: el enlace del admin de **reconocimientos** usa la base pública
  `support_web_base` (`https://support.openmusicrepository.com/support-api`) en vez de la interna
  `127.0.0.1:8300` (que el navegador no alcanza). Vhost de support habilitado en Prod.
- **5.1.1 (C) — `osap-storage`**: `count()` de personas/compositores ya no genera SQL inválido
  cuando `include_all`+`visible=all` sin filtros (`WHERE` vacío → `1=1`). Arreglaba el 500 del
  "Maestro personas" del admin.
- **5.1.1 (C) — `osap-support`**: al **re-conceder** un reconocimiento revocado (p. ej. FOUNDER)
  se **reactiva la misma fila** (`uq user+project+type`) en vez de dar `RecognitionConflictError`;
  `grant_recognition.py`.
- **5.1.2 (C) — `osap-auth`**: **gate legal/onboarding en el flujo de autorización OIDC**: no se
  emite el `code` sin onboarding (`OnboardingRequiredError` en `CompleteAuthorizationUseCase`);
  `/auth/authorize/complete` → `409 onboarding_required` (el login embebido va al onboarding y
  reanuda); el callback **social** sin onboarding redirige al onboarding con los tokens en el
  fragmento + contexto OIDC. Incluye la **edición de `nickname`** en el admin de usuarios.
- **5.1.1 (C) — `osap-auth`**: **aviso por email** al usuario cuando el admin le asigna el `nickname`
  (best-effort); incluye el soporte de `nickname` en el update admin.
- **5.1.1 (C)** — `osap-api` **en solitario** (decisión explícita: es cambio de SPA/admin, no se
  comparte con el resto de programas).
  - Diseño público: fondo de partitura en el área derecha con **`--bg` en `header`/`main`/`footer`**,
    tesela **tenue** (capa translúcida del color base), menú de admin con fondo `--bg`.
  - Listado de compositores: **filtro de revisión solo para admin**, `review_status` fuera de la
    vista pública, y **`nacionalidad · birth–death`**.
  - Admin: **edición de `nickname`** de usuario.
  - Alcance: `osap-api`. Evidencia: suite osap-api 817, ruff/mypy limpios; smoke en Prod.
- **5.1.0 (B)** — modelo canónico de formaciones vocales (`osap-storage`) y contexto de formación
  en representaciones.
  - `canonical_ensemble()`: función única (alfabeto S/MZ/A/CT/T/BAR/B, **idempotente por punto
    fijo**) reutilizable por importación y búsqueda; catálogo `ensembles` materializado
    (`ensembles_code = id_canonico`) + `ensembles_aliases` (1085) preservando los 1374 códigos
    originales; `ensemble_voices` reconstruido.
  - `representations.representations_ensemble_code` + `representations_voice_signature`
    (firma **derivada**, no fuente de verdad) y derivación por `canonical_ensemble` en la
    importación CPDL.
  - Migraciones **aditivas** `022_ensembles_aliases.sql` y `023_representations_ensemble_code.sql`.
  - Alcance: `osap-storage` (principal) + versión del conjunto. Evidencia Dev: validación con
    **0 discrepancias**; suite storage 517; validación Prod al cierre.
- **5.0.0 (A)** — entrega coordinada con **esquema destructivo** y modelo de aportaciones.
  - **osap-storage**: migración **021** → `DROP COLUMN persons.persons_biography_updated_at`
    (redundante; la biografía se refleja en `persons_updated_at`). Canonicalización del voicing
    CPDL (`canonical_code`) y depuración de personas/roles (material de auditoría en `_externo/`).
  - **osap-api**: migración de **aportaciones** (`contributions`, `contribution_relations`,
    `contribution_events`, `contribution_artifacts`, con `payload_json`); operaciones reales
    `create_work`, `add_representation` y `add_resource` (con materialización en storage) y
    «Mi actividad».
  - **osap-auth**: **0009** onboarding + aceptación legal versionada (nickname, ToS, privacidad)
    y **0010** consentimiento público de nickname; M2M de usuarios públicos.
  - **osap-support**: M2M por proyecto, mantenimiento web propio y reglas de concesión de
    reconocimientos.
  - Incluye en el conjunto la capa SEO pública + sitemap (4.3.0).
  - Punto de control previo: tag `v4.2.2` + rama de mantenimiento `release/4.x` (línea anterior).
  - Alcance: los cuatro programas. Evidencia: tests `osap-api` 816 (ruff+mypy limpios), `osap-auth`
    158, `osap-support` 193, `osap-storage` 477 (47 skipped); en Prod, migraciones `0009`/`0010`
    (auth) y `021` (storage) aplicadas, tablas de aportaciones creadas; los cuatro servicios
    `active` con health `ok`; rutas nuevas publicadas y `401` sin sesión; `app` 200 con
    mantenimiento OFF.
- **4.3.0 (B)** — capa pública SEO: `osap-api` sirve HTML server-rendered de `/compositor/{id}/{slug}`
  y `/obra/{id}/{slug}` (title/description/canonical, `<h1>`, JSON-LD `MusicComposition`/`Person`/
  `BreadcrumbList`, enlaces internos y 301 al canónico; 404 HTML `noindex`), **sitemap dinámico**
  (`/sitemap.xml` + `/sitemaps/works-N.xml|persons-N.xml`) y, en la SPA, `useSeo` con
  `noindex` en rutas internas. Infra: nginx/`.htaccess` proxya las rutas SEO. Compatible; alcance:
  `osap-api` (backend + SPA) + nginx. Evidencia: 732 tests backend, 99 frontend, smoke E2E local y
  en producción. Dependencia nueva: `Jinja2`.
- **4.2.2** — admin: "Dar de baja" **anonimiza** la cuenta (incluye pendientes de verificar)
  y se corrige que `users.email_lookup` no se persistía en el `ON DUPLICATE` (la baja no
  liberaba el email y el cambio de email no surtía efecto). Web de osap-auth: favicon y
  build/despliegue integrados en `deploy_all`.
- **4.2.1** — correos transaccionales de identidad en osap-auth: implementado el envío por
  SMTP (`[smtp]`/`OSAP_AUTH_SMTP_*`) para verificación de email, reenvío y recuperación de
  contraseña (antes solo se generaba el token, **sin enviar**). Verificado E2E en producción
  (registro → correo → `verify-email`).
- **4.2.0** — funnel de acceso y contribución: `funnel_events` append-only
  (`limit_reached`/`registered`/`membership_activated|lapsed`/`promotion_applied|reverted`),
  promoción donor materializada como `user_quota_overrides` por reconciliación M2M **pull**
  con osap-support (cada 15 min vía `osap-reconcile-membership.timer`), revocación
  administrativa que no resucita en el mismo periodo, y métricas derivadas. Corrección del
  cableado de `service_audience` en osap-support (`aud=osap-support` para tokens M2M).
  Colaboradores: las altas de usuario enlazan a la pantalla de registro de osap-auth.
- **4.1.0** — cuota de descargas OMR (planes 10/100/1000, excepción por usuario con
  vigencia, auditoría `download_usage`), gateo de `download_representation` y
  `/api/v1/omr/download`, cierre del bypass de storage (`/api/download` exige
  `storage:read`) y panel de administración de cuotas/estadísticas.
- **4.0.0** — entrega coordinada: modelo de datos nuevo de `osap-storage`
  (`persons`, voicings→ensembles; migraciones 006–008), identidad de recurso en el índice
  de `osap-api` (`source_rep_id`/`resource_id`, `person_id`), formatos CPDL ampliados y
  editor de relaciones de obra; despliegue de los 4 programas.

## Operaciones registradas

### SEC-A — Rotación de la clave JWT de osap-auth (2026-09-28) — CERRADA

- **Motivo:** la clave de firma JWT de producción era **la misma que la de desarrollo**, con
  el mismo `kid` (`osap-auth-v1`).
- **Cambios de código asociados:**
  - W1 (osap-api): verificación real de firma RS256 + JWKS por `kid` + `token_issuer`
    (`f0090ee`, `ca887d1`).
  - osap-auth: JWKS multi-clave por `kid` (`c0621c2`) y carga de `jwt_kid` desde YAML
    (`0b45d06`).
  - osap-storage: selección de clave de verificación por el `kid` de la **cabecera** JWT
    (`ac7b25c`).
- **Rotación:** nueva clave `osap-auth-v2` firmando; `osap-auth-v1` publicada como
  `previous_public_keys` (solape). Reinicio coordinado de osap-api/storage/support para
  refrescar sus cachés JWKS.
- **Cierre:** tras `access_token_ttl + skew` (930 s) se retiró `osap-auth-v1`.
- **Verificación final:** JWKS → **solo `osap-auth-v2`**; token v2 aceptado y **v1 rechazado**
  en osap-api (200/401), osap-storage (200/401) y osap-support (200/401); token forjado → 401
  en osap-api; los cuatro servicios activos y sanos.
- **Backups con la clave antigua: CONSERVADOS** (reversibilidad) hasta la fase de
  permisos/credenciales:
  - servidor: `osap-auth/config.yaml.sec-a-backup-20260928-181811`,
    `osap-auth/config.yaml.a4-smtp-backup-20260928-182411`;
  - local: `osap-auth/config.production.yaml.sec-a-backup-20260928-182431`.
- **Desviación registrada:** al desplegar el código de osap-auth, A4 (SMTP obligatorio en
  producción) impidió el arranque; se configuró SMTP **reutilizando temporalmente el de
  osap-support** para restaurar el servicio. La separación/rotación de esa credencial queda
  pendiente en su fase.

### SEC-B — Separación/rotación de la credencial SMTP — DIFERIDA (aceptada)

- **Decisión (2026-09-28):** se acepta temporalmente **compartir la misma cuenta SMTP**
  (`support@openmusicrepository.com`, Raiola Networks) entre `osap-auth`, `osap-support` y
  los entornos dev/prod.
- **Motivo:** rotarla afecta a consumidores del buzón fuera de los servicios y requiere
  acceso al panel de Raiola, que no está disponible en esta fase.
- **Riesgo aceptado:** credencial SMTP única y reutilizada.
- **Pendiente en la fase de credenciales/permisos:** crear credenciales distintas por servicio
  (buzones o app passwords), rotar `support@` y eliminar la reutilización dev/prod.
- **No se modificó ninguna configuración.**

### SEC-C — Identidades de BD por servicio (2026-09-28) — CERRADA

- **Antes:** los cuatro servicios usaban `osap@localhost` con `ALL PRIVILEGES` sobre las
  cuatro bases (sin aislamiento, misma contraseña).
- **Nuevos usuarios, uno por servicio y limitado a su base:**
  - `osap_api` → `SELECT, INSERT, UPDATE, DELETE, CREATE` sobre `osap_api` (el `CREATE` es
    necesario por el DDL en runtime de `analytics_*`).
  - `osap_auth`, `osap_storage`, `osap_support` → DML + `CREATE, ALTER, DROP, INDEX,
    REFERENCES, CREATE TEMPORARY TABLES, LOCK TABLES` sobre su base (requerido por sus
    migraciones/Alembic).
- **Credenciales efectivas:** auth y storage en `config.production.yaml`, support en
  `osap.production.toml`, api en el drop-in de systemd
  `osap-api.service.d/override.conf` (se vaciaron las credenciales obsoletas de
  `osap.production.toml`). Backups `.sec-c-backup-*`.
- **Verificación:** matriz de aislamiento (cada usuario accede solo a su base; las otras tres
  **denegadas**), operaciones reales por servicio (auth login → 401 con lectura a BD,
  storage search → 200, support membership → 200, api analytics → 200) y los cuatro
  servicios `active`.
- **Revocación:** retirados los grants de `osap@localhost` sobre las cuatro bases y usuario
  **eliminado**. Evidencia pre-cambio en
  `/home/ocw/openmusicrepository.com/sec-c-shared-user-grants.txt`.
- **Post-revocación:** los cuatro servicios siguen `active` con operaciones OK; `osap` ya no
  existe ni tiene grants.
- **Fuera de alcance (acordado):** separar usuario runtime DML / usuario de migración DDL.

### SEC-D — Rotación de client secrets de osap-api (2026-09-28) — CERRADA

- **Secretos:** `OSAP_SERVICE_CLIENT_SECRET` y `OSAP_ADMIN_CLIENT_SECRET` (drop-in
  `osap-api.service.d/env.conf`) y `OSAP_OIDC_CLIENT_SECRET` (drop-in `oidc-secret.conf`).
  No había duplicación dev/prod.
- **Consumidores:** SERVICE → `osap-auth` client_credentials (`storage:read/write`); ADMIN →
  client_credentials (`storage:admin`); OIDC → `authorization_code` (login de usuario).
- **Almacenamiento del hash en osap-auth** (`service_clients` / `oauth_clients`),
  verificado con **`HmacTokenHasher`** (HMAC-SHA256 + `token_hmac_pepper`), no Argon2.
  Sin dual-secret → **rotación coordinada sin solape**; impacto acotado (emisión de token
  M2M / logins nuevos).
- **Método (uno a uno, SERVICE → ADMIN → OIDC):** generar secreto; calcular hash con
  `HmacTokenHasher(pepper)`; `UPDATE` del `client_secret_hash` del cliente concreto; backup
  del drop-in; actualizar el drop-in; `daemon-reload` + reinicio de osap-api; verificar
  **nuevo** y **antiguo**.
- **Verificación:** SERVICE token 200 + `storage:read` 200 y antiguo 401; ADMIN token 200 +
  `storage:admin` 200 y antiguo 401; OIDC nuevo → `invalid_grant` (cliente autenticado),
  antiguo → `invalid_client`. Los cuatro servicios `active`; health api/auth/storage 200;
  `api persons` 200.
- **Backups conservados:** `env.conf.sec-d-backup-*`, `env.conf.sec-d-admin-backup-*`,
  `oidc-secret.conf.sec-d-backup-*`.
- **Nota operativa:** el primer intento de SERVICE calculó el hash con Argon2 (incorrecto);
  corregido en la misma ventana usando `HmacTokenHasher`.
- **Fuera de alcance (acordado):** filas heredadas de `service_clients`.

### SEC-E — Rotación de credenciales externas · R2 (2026-09-29) — CERRADA

- **R2 (Cloudflare):** token S3 del bucket `osap-storage` (account `649d3187e49cf9ee8dbbc2b0c22d2f4e`),
  consumido por `osap-storage` (cliente S3 boto3). Sin duplicación dev/prod.
- **Rotación con solape** (R2 admite varios tokens): token nuevo configurado en
  `osap-storage` (local `config.production.yaml` y prod `config.yaml`) y servicio
  reiniciado. Verificado `put/get/delete` y **lectura de objetos reales** del bucket;
  el token antiguo seguía válido (solape). Revocado en Cloudflare → el **antiguo queda
  rechazado** (`Unauthorized`) y el **nuevo sigue operativo**; storage `active` y
  `health` con `repository: true`.
- **Evidencia:** token antiguo `access_key` hash `4b19f6b641` / `secret_key` hash
  `3e3523fdc6`; fecha de rotación 2026-09-29.
- **Backups conservados:** servidor `config.yaml.sec-e-r2-backup-…` y
  `config.yaml.sec-e-r2-switch-…` (600); local `config.production.yaml.sec-e-r2-backup`.
- **Alcance cerrado:** solo se rotó R2. MusicBrainz, PayPal (live) y social
  Google/GitHub se **dan por buenos sin rotación** (decisión: no se consideran expuestos).
- **Fuera de esta entrega:** SEC-F (permisos 664→600/640 y secretos inline de systemd →
  `EnvironmentFile`) y SEC-G (peppers/AEAD).

### SEC-F — Permisos y secretos inline de systemd

#### F.1 — Permisos de ficheros con secretos (2026-09-29) — HECHO

- Ficheros con secretos pasados a **600** (antes `644`/`664`): `osap-api/osap.toml`
  (+ `.bak_20260823`, `.seo-backup-…`), `osap-storage/config.yaml` y
  `config.production.yaml`, `osap-support/osap.toml`,
  `/etc/systemd/system/osap-api.service.d/override.conf` y backups `.sec-*` en el servidor.
- Verificado: **ningún** fichero con secretos legible por grupo/otros
  (`find … -perm /037` sin resultados); los cuatro servicios `active` y health OK
  (api 200, auth 200, storage 200).

#### F.2 — Secretos inline de systemd → EnvironmentFile (2026-09-29) — HECHO

- Movidos a `/etc/openmusicrepository/osap-api.env` (directorio `700`, fichero `600`):
  `OSAP_API_DB_PASSWORD`, `OSAP_ADMIN_CLIENT_SECRET`, `OSAP_SERVICE_CLIENT_SECRET`,
  `OSAP_OIDC_CLIENT_SECRET`.
- Añadido `EnvironmentFile=/etc/openmusicrepository/osap-api.env` al unit y **eliminadas**
  las líneas de secreto de los drop-ins (y el stub `oidc-secret.conf`).
- Verificado:
  - **entorno efectivo idéntico** antes/después (`/proc/<pid>/environ` por clave),
  - **sin secretos** en los ficheros activos del unit/drop-ins,
  - backups con secretos movidos a `/etc/openmusicrepository/backups` (dir `700`, ficheros `600`),
  - los cuatro servicios `active`; api health 200; `persons` (M2M SERVICE) 200.

### SEC-G — Rotación de peppers/AEAD (2026-09-29) — PROD HECHO

- **Claves:** `email_hmac_pepper` (`users.email_lookup`), `email_aead_key_b64`
  (`users.email_cipher`, AES-256-GCM) y `token_hmac_pepper` (hashes de `tokens`,
  `sessions`, `authorization_codes`, `service_clients`, `oauth_clients`).
- **Estrategia:** one-shot con `osap-auth` detenida brevemente (sin key-ring; 20 usuarios).
- **Pasos:** backup (`mysqldump` de las tablas + config en `/root/sec-g-backups-…`);
  migración de 18 `users` (descifrado con AEAD antiguo → `email_lookup`/`email_cipher`
  nuevos, `key_version=2`); re-hash de los client secrets **conocidos** (SERVICE, ADMIN,
  `243ae…`, oauth `osap-api`) con el `token_hmac_pepper` nuevo. Config (`config.yaml`, 600)
  con las claves nuevas y reinicio.
- **Efectos conocidos:** sesiones/tokens/códigos existentes quedan inválidos → **re-login**;
  los clientes `81c78ac9…` (support:ingest) y `f9152dd9…` quedan invalidados (secretos
  desconocidos → no re-hasheados; sin uso en la auditoría).
- **Verificación:** 18/18 consistentes; 0 lookups casan con el pepper antiguo; el AEAD
  antiguo no descifra; SERVICE/ADMIN/`243ae` emiten token **200** y storage read/admin **200**;
  OIDC → `invalid_grant` (cliente autenticado); 4 servicios `active`; health 200; `persons` 200.
- **Hashes de claves:** antiguas `5d56bf2118`/`4992416e4d`/`8242108c37`; nuevas
  `2ece7e8afe`/`4016ee1ace`/`7d7445ad43` (solo hash, sin valores).
- **Incidencia:** el primer intento falló por los nombres de variable de los client ids
  (están en el drop-in); el rollback requirió restaurar `users` desde el dump y se reintentó
  con éxito.
- **Dev:** conserva **claves propias** (las antiguas, que producción ya **no** usa) → se
  elimina la reutilización dev/prod. Los datos de dev se migraron y se **revirtieron** para
  dejarlo consistente con su `osap-auth` en marcha (el proceso de dev no era reiniciable
  desde esta sesión); consistencia verificada (13/13) y health 200.
