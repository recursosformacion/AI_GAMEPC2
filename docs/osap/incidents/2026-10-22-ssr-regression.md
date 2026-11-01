# Incidente 2026-10-22 — fichas de obra en SPA

## Impacto

- Search Console: pico de **181 clics** el 22/10 y **6 clics** el 23/10.
- Googlebot pasó de ~43.405 respuestas 200 el 21/10 a ~9.472 el 22/10 y ~4.616 el 23/10.
- Las fichas `/obras/...` dejaron de entregar contenido, canonical y JSON-LD en el HTML inicial.

## Causa

El despliegue de 5.6.0 (`efe899c`) cambió nginx para servir `/obras/` con:

```nginx
location ^~ /obras/ {
    try_files $uri $uri/ /index.html;
}
```

La SPA nueva era visualmente correcta, pero Googlebot recibía el shell de React. Además,
algunos IDs del índice antiguo respondían 404 en la API. No fue una caída del servidor.

## Corrección

- Las fichas de obra y compositor se enrutan al `osap-ssr` de Node (`57c3047`).
- El canonical de obra conserva `index-<id>` y el slug del sitemap.
- La clasificación (`/genres`, `/catalogues`, `/epochs`, `/ensembles`, `/instruments`) usa SSR
  con los listados precargados (`2cdaaf2`).
- `/representacion/...` usa SSR con contenido y metadatos (`243cbe5`).
- El sitemap actual se validó y se lanzó en Search Console.

## Prevención

1. **Ninguna ficha pública se sirve solo como SPA.** Las rutas de detalle deben tener SSR o
   prerender con contenido en la primera respuesta.
2. Ejecutar `script/smoke-seo.ps1` después de cada despliegue y antes de anunciar una release.
3. No hacer builds manuales sin `VITE_BLOG_URL` y `VITE_VIDEOS_URL` de producción; usar
   `script/deploy.ps1`/`deploy_all.ps1`.
4. Cualquier cambio de IDs, slugs o URLs exige tabla de correspondencia y 301; ver
   `AGENTS.md` y `docs/osap/versioning.md`.
5. Revisar en Search Console “Indexación de páginas” y “Rastreo” 24–72 h después de cada
   cambio de rutas públicas.

## Seguimiento

- Solicitar indexación de las URLs principales en Search Console.
- Vigilar la recuperación de clics y el rastreo durante 2–6 semanas.
- Resolver los `index-*` históricos con un mapa de alias si se recupera el sitemap antiguo.
