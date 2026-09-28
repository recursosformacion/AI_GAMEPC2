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
