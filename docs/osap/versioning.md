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
