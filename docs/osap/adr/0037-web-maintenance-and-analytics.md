# ADR-0037 – Web: modo mantenimiento y analítica de SPA (GTM)

## Estado

Aceptado (2026-09-12). Carril independiente (no forma parte de F0–F5). Cubre dos decisiones
de operación de la web (`osap-api/web`, servida por Apache desde `web/dist`).

## Contexto

1. Al publicar una versión hay que cortar el acceso público, pero el equipo necesita revisar
   la web desplegada antes de liberarla.
2. Google Tag Manager carga el contenedor `GTM-WR6VXCFD`, pero no recibe datos: la app es una
   SPA con React Router, no hay recargas de página y **nada empujaba eventos a `dataLayer`**
   más allá del `gtm.js` inicial.

## Decisión

### D1 — Mantenimiento en la capa Apache, no en el SPA

- `web/public/maintenance.html` es una página estática autocontenida, con `noindex`.
- `web/public/.htaccess` añade:
  - `ErrorDocument 503 /maintenance.html`.
  - Bypass permanente para assets (`/assets/`, favicon, robots, sitemap) y para
    `maintenance.html`.
  - **Fallback SPA propio** (`!-f`/`!-d` → `/index.html`): al definir `RewriteRule` en
    `.htaccess` se **reemplaza** el del vhost, así que el fallback debe estar aquí o las
    rutas profundas (`/viewer`, `/explore`…) devolverían 404.
  - Corte 503 solo si existe `maintenance.flag` **y** no hay cookie `osap_preview`; el bypass
    de revisión no usa `[L]` (cortaría el fallback).
- Flag y token viven en `web/dist` (no versionados): `maintenance.flag` / `maintenance.token`.
- `web/scripts/maintenance.ps1` (`-On`, `-Off`, `-Status`) crea/borra el flag y imprime la
  URL de revisión con token estable.

**Por qué en Apache:** el corte debe existir incluso si el JS no carga; y no debe requerir
reconstruir el bundle para activar/desactivar.

### D1b — Producción (nginx): mismo contrato

Producción sirve la SPA con **nginx** (no honra `.htaccess`). El vhost se versiona en
`deploy/app.openmusicrepository.com.conf` y lo instala `script/deploy.ps1` (scp + `nginx -t`
+ reload). Reglas:

- `error_page 503 /maintenance.html` + `location = /maintenance.html` (sirve el fichero).
- En `location /` y `location = /index.html`: si existe
  `/home/ocw/openmusicrepository.com/app/maintenance.flag` y no hay cookie
  `osap_preview=1` (ni ruta exenta: assets, favicon, robots, sitemap), responde **503**.
- `/api/`, `/auth/`, `/support-api/`, `/docs` NO se cortan: permiten verificar los servicios
  durante el mantenimiento, justo antes de liberar.
- `deploy.ps1` excluye `maintenance.flag` y `maintenance.token` del `dist.tar.gz` para no
  activar mantenimiento por accidente al desplegar.

`web/scripts/maintenance.ps1` gestiona ambos entornos (`-On`/`-Off`/`-Status`, con
`-LocalOnly`/`-RemoteOnly`): flag local (`web/dist`) y flag remoto por SSH (`RemoteIA`).

### D2 — Analítica: eventos `dataLayer` desde la SPA

- `web/src/analytics/gtm.ts` expone `pushEvent(event, params)` y
  `trackPageView(path)` (`window.dataLayer` garantizado).
- `Layout` (que ya usa `useLocation`) envía `page_view` en cada cambio de ruta.
- **Acción requerida en GTM (fuera del repo):** crear un *trigger* de tipo *Custom Event* con
  nombre `page_view` y una etiqueta GA4 que lo dispare. Sin ese trigger, el contenedor recibe
  el evento pero no lo reenvía a GA4; el `page_view` inicial lo emite la etiqueta de
  configuración de GA4.

## Consecuencias

- El mantenimiento no depende del build ni del backend; el bypass es por cookie de un día.
- El token no es un secreto criptográfico: es una conveniencia operativa. Quien lo reciba
  puede revisar la web en mantenimiento (contenido ya público). Rotarlo = borrar
  `maintenance.token` y volver a `-On`.
- Instrumentar eventos de negocio (búsqueda, descarga, votos) es incremental: basta llamar a
  `pushEvent` y crear sus triggers/etiquetas en GTM.
