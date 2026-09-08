# PENDIENTES — Liberación a REAL (v1 corregida)

> Archivo de dudas/decisiones para cuando Miguel vuelva. Los cambios de v1 están
> commiteados y pusheados a `origin/main` en cada repo (ver abajo). NO se ha desplegado
> a producción todavía.

## Commits subidos (2026-09-08, sesión autónoma)
- osap-api: `8125fc8` — cierre v1 (auth OIDC/admin usuarios, soporte, correcciones búsqueda/proveedores, auth proxy `Bearer`/`/auth`).
- osap-auth: `731875b` — desacoplar osap-api local (instalación runtime en servidor).
- osap-support: `e9ff4fc` — identidad real en dev (`DevIdentityResolver`) y PayPal sandbox opt-in por config (`[paypal] dev_real`).
- osap-storage: `6c6d0e0` — catálogo compositores (cpdl/epochs/géneros/instrumentos), admin CRUD y streaming R2.

## Dudas / decisiones pendientes para «liberar a REAL»
1. **Alcance del despliegue**: ¿se despliegan los 4 repos a la vez? En concreto osap-storage
   lleva **migraciones SQL 031–041** (cpdl, epochs, géneros, instrumentos, backfills) que
   aún no sé si están validadas contra la BD de producción. Recomiendo desplegar
   osap-storage con cuidado (migraciones + reindex) o diferirlo.
2. **PayPal**: ¿producción debe pasar a **live** (dinero real) o seguir en sandbox?
   El `osap.production.toml`/config de prod del servidor debe contener credenciales y
   `plan_ids` reales; en local no existe ese fichero (no tocar).
3. **Webhooks PayPal en dev**: la activación de suscripciones/donaciones depende de que
   PayPal alcance una URL HTTPS pública. El Apache local (XAMPP) no da HTTPS. Para probar
   en dev: túnel HTTPS (cloudflared/ngrok) → `127.0.0.1:8300/support-api/api/v1/webhooks/paypal`
   y apuntar ahí el webhook de la app Sandbox. En prod el webhook debe apuntar al host real
   (`support.openmusicrepository.com`/nginx), no a `omr.servebeer.com` (HTTP sin TLS).
4. **Verificación post-despliegue**: Admin → Usuarios en prod requiere **login real OIDC**
   con cuenta admin (el bypass dev no vale). Probar listar, deshabilitar/habilitar y
   Ver/Editar tras el deploy.
5. **storage provider dev → R2**: se dejó apuntando a R2 (`path_prefix=storage2017`) para
   que la BD dev suba tal cual a prod. Verificar que no haya datos dev mezclados.
6. **osap-compositores**: no se ha tocado (sin cambios).
7. **Layout admin (en curso)**: se está migrando `/admin/*` a un `AdminLayout` con sidebar
   vertical izquierdo a pantalla completa; cuando esté, se añadirá el listado de pagos.
