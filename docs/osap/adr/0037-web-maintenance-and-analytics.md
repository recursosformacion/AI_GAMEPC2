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
  - Bypass de revisión: llegar con `?preview=<TOKEN>` deja la cookie
    `osap_preview=1` (1 día, `SameSite=Lax`). Con cookie, Apache no aplica el corte.
  - Si existe `%{DOCUMENT_ROOT}/maintenance.flag`, el resto de rutas responde **503** con la
    página de mantenimiento (correcto para SEO: no es un 200 con contenido de error).
- Flag y token viven en `web/dist` (no versionados): `maintenance.flag` / `maintenance.token`.
- `web/scripts/maintenance.ps1` (`-On`, `-Off`, `-Status`) crea/borra el flag y imprime la
  URL de revisión con token estable.

**Por qué en Apache:** el corte debe existir incluso si el JS no carga; y no debe requerir
reconstruir el bundle para activar/desactivar.

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
