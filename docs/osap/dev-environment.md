# Entorno de desarrollo de OSAP

> **IMPORTANTE (léeme antes de tocar el frontend o levantar servicios):**
> El flujo de desarrollo **no usa `vite dev`**. Se sirve con **Apache (XAMPP)** bajo el
> VirtualHost `osap-app`, que sirve el build estático `web/dist` y proxya `/api` al backend.
> Levantar `vite dev` en 5173 es **innecesario y confuso**: la app se abre en
> `http://osap-app`, no en `localhost:5173`.

---

## Arquitectura de servicios en desarrollo (localhost)

```
http://osap-app                     Apache (XAMPP) — VirtualHost *:80
   │   ServerName: osap-app
   │   DocumentRoot: D:/Proyectos/AI_OSAP/osap-api/web/dist      (SPA estática)
   │   RewriteRule ^ /index.html [L]                        (SPA fallback)
   │
   ├─ /api/*            → ProxyPass → http://127.0.0.1:8001/api/   (backend uvicorn)
   ├─ /obras/*, /composers/*, /representacion/*, /amigos/* → osap-api (HTML SEO server-rendered, `api/http/seo.py`)
   ├─ /sitemap.xml, /sitemaps/* → osap-api (sitemaps dinámicos, `api/http/sitemap.py`)
   ├─ /docs             → ProxyPass → http://127.0.0.1:8001/docs
   ├─ /openapi.json     → ProxyPass → http://127.0.0.1:8001/openapi.json
   └─ /redoc            → ProxyPass → http://127.0.0.1:8001/redoc
```

- **Frontend** servido por Apache desde `web/dist` (build de producción de Vite).
- **Backend** (API) en uvicorn `127.0.0.1:8001`.
- Apache hace de reverse-proxy para `/api`, `/docs`, `/openapi.json`, `/redoc`.

### Hosts del proyecto (en `C:\Windows\System32\drivers\etc\hosts`)

| Host | Uso |
|---|---|
| `osap-app` | **Cliente web OSAP** (SPA + proxy /api) — la app en la que trabajamos |
| `osap-api` | Backend API (uvicorn 8001) |
| `osap-storage` | Open Music Repository / storage (uvicorn 8000) |
| `osap-blog` | Blog independiente (uvicorn 8500, VirtualHost Apache) |
| `ai-publicidad` | Publicidad local (uvicorn 8305; panel `/admin` con token local) |
| `ai-noticias` | Corpus de noticias de solo lectura (uvicorn 8401; API interna con `X-OSAP-News-Token`) |
| `chorus` | Área de trabajo y mensajería de grupos (uvicorn 9600; migraciones SQLite al arrancar) |

Todos apuntan a `127.0.0.1`.

`restart-dev.ps1` marca explícitamente `OSAP_ENV=development` y
`OSAP_DEPLOYMENT=development` para osap-api, además de `OSAP_AUTH_ENV=development`
y `OSAP_SUPPORT_ENV=development`; así el marcador de despliegue no puede prevalecer
desde un entorno heredado. Los servicios arrancan en modo producción por defecto
cuando no hay un marcador de desarrollo. También arranca `ai-noticias` en 8401, `chorus` en 9600 y pasa a osap-api
`OSAP_NEWS_API_BASE`/`OSAP_NEWS_API_TOKEN`. También reparte
`OSAP_INTERNAL_SERVICE_TOKEN` entre auth/support/api para el boletín. La lectura de
noticias usa la sesión OSAP (`/noticias`); el correo no es una vía de acceso. Detalle en
[`news-integration.md`](news-integration.md) y [`news-digest.md`](news-digest.md).

---

## Modo túnel: desarrollo contra la BD real (solo lectura)

Con `[osap] dev_mode = 1` la API y la SPA trabajan con los **datos reales** de la BD
operativa y se garantiza el **solo lectura**. Los servicios HTTP (storage y auth) siguen
siendo **locales**: no se llama al storage de producción ni se necesitan credenciales de
servicio.

- **BD**: `[db]` de `osap.toml` apunta al túnel, no al MySQL local:

  ```toml
  [db]
  host = "127.0.0.1"
  port = 3307
  name = "osap_api"
  user = "osap_ro"
  password = "<clave de osap_ro>"
  ```

  `db.port` permite convivir con el MySQL local en 3306 (dev_mode = 0).

- **Túnel**: `ssh -N -L 3307:127.0.0.1:3306 RemoteIA`. Se abre **a mano** con
  `script/osap-tunnel.ps1 -Start` solo cuando se quiere conectar dev a remoto. La tarea
  programada ya no lo abre por defecto.
  Comprobar: `Test-NetConnection 127.0.0.1 -Port 3307`.

- **Servicios locales**: osap-storage (`config.yaml` con `name: osap_storage`, `user: osap_ro`,
  `port: 3307`) y osap-auth escuchan en `127.0.0.1:8000` y `127.0.0.1:8200`. `osap.toml`
  fuerza que la API use esas rutas:

  ```toml
  [osap]
  dev_mode = "1"
  storage_base_url = "http://127.0.0.1:8000"
  storage_web_base = "http://127.0.0.1:8000"
  auth_token_url = "http://127.0.0.1:8200/oauth/token"
  auth_base_url = "http://127.0.0.1:8200"
  ```

  Así el comportamiento es local y **no hay `[service]`** ni secretos de producción.

- **Fallo rápido**: si `dev_mode = 1` y el puerto de `[db]` no acepta conexión, `wire()`
  aborta el arranque con un `ConfigurationError` que recuerda el comando del túnel. No se
  degrada en silencio a memoria ni a la BD local.

- **Solo lectura**: el usuario `osap_ro` solo tiene `SELECT` sobre `osap_api` y
  `osap_storage`. Los stores MySQL reciben `read_only=True` y **no ejecutan DDL**
  (`CREATE TABLE IF NOT EXISTS` daría error 1142 y la factoría caería a memoria perdiendo
  la configuración real).

- **Aviso**: `/api/v1/system/health` devuelve `"mode": "dev-real"`,
  `"storage_target": "local"` y `read_only: true`; la SPA muestra el banner
  «Producción · solo lectura».

Para volver al modo local: `dev_mode = 0` y `[db]` con el MySQL local (`port = 3306`).

---

## Flujo de trabajo (siempre)

### 1. Backend (Python) — uvicorn en el puerto 8001

```powershell
python -m uvicorn --factory src.osap.api.platform_app:create_platform_app --host 127.0.0.1 --port 8001
```

- Cualquier cambio en `src/osap/` **requiere reiniciar uvicorn** (o usar `--reload`).
- Verificación: `http://osap-app/api/v1/system/health` → `{"success":true,...,"status":"ok"}`.

### 2. Frontend (web/) — SIEMPRE rebuildar `web/dist`

```powershell
cd web
.\node_modules\.bin\tsc.cmd --noEmit        # typecheck (opcional, recomendado)
node node_modules/vite/bin/vite.js build    # genera web/dist
```

- Atajo: `pwsh script/restart-dev.ps1 -Build` recompila la SPA (tsc + vite) y reinicia los
  servicios de una vez (evita olvidar el rebuild tras editar `web/src`).
- `web/dist` es lo que sirve Apache. **No** usar `npm run dev` ni `pnpm dev`.
- Apache sirve `web/dist` en tiempo real: tras el build basta **recargar `http://osap-app`**
  (con cache limpia / Ctrl+F5), **no** hay que reiniciar Apache por cambios de frontend.
- Nota: `npm run dev` falla porque el hook de pnpm lanza `pnpm install` y esbuild tiene el
  build ignorado (`ERR_PNPM_IGNORED_BUILDS`). Por eso se invoca `node node_modules/vite/bin/vite.js build` directamente.

### 3. Verificación final

- Abrir `http://osap-app` en el navegador (no `localhost:5173`).
- Comprobar `/api` mediante el proxy: `http://osap-app/api/v1/system/health`.

---

## No hacer (errores pasados)

- ❌ NO levantar `vite dev` (5173) creyendo que es el entorno: la app real está en `osap-app`.
- ❌ NO editar `web/src/...` y esperar que se vea sin rebuildar `web/dist`.
- ❌ NO asumir que el frontend se sirve desde FastAPI: el backend **no** monta estáticos;
  quien sirve la SPA es Apache.

---

## Config de Apache (referencia)

Fichero: `C:\xampp\apache\conf\extra\httpd-vhosts.conf`
(bloque `osap-app`, líneas 81–106). Requiere módulos `mod_proxy` y `mod_rewrite` activos
en `C:\xampp\apache\conf\httpd.conf`.

```
<VirtualHost *:80>
    ServerName osap-app
    DocumentRoot "D:/Proyectos/AI_OSAP/osap-api/web/dist"
    <Directory "D:/Proyectos/AI_OSAP/osap-api/web/dist">
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
        RewriteEngine On
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteRule ^ /index.html [L]
    </Directory>
    ProxyPass /api/ http://127.0.0.1:8001/api/
    ProxyPassReverse /api/ http://127.0.0.1:8001/api/
    ProxyPass /docs http://127.0.0.1:8001/docs
    ProxyPass /openapi.json http://127.0.0.1:8001/openapi.json
    ProxyPass /redoc http://127.0.0.1:8001/redoc
    ErrorLog "logs/osap-app-error.log"
    CustomLog "logs/osap-app-access.log" combined
</VirtualHost>
```

El blog independiente se sirve en `http://osap-blog` (uvicorn 8500):

```
<VirtualHost *:80>
    ServerName osap-blog
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8500/
    ProxyPassReverse / http://127.0.0.1:8500/
</VirtualHost>
```

La SPA enlaza al blog desde el ítem «Blog» del menú lateral. El build de producción define
`VITE_BLOG_URL=https://blog.openmusicrepository.com` en `script/deploy.ps1` y
`script/deploy_all.ps1`.

---

## Capa pública SEO (/obras y /composers)

Las URLs indexables de entidad las sirve **osap-api** con HTML server-rendered
(`src/osap/api/http/seo.py` + plantillas en `src/osap/api/templates/`). No forman parte de
`/api` y no las renderiza la SPA:

- `/composers/{person_id}` → 301 a `/composers/{person_id}/{slug}`
- `/composers/{person_id}/{slug}` → ficha HTML (biografía + obras + JSON-LD)
- `/obras/{work_id}` → 301 a `/obras/{work_id}/{slug}`
- `/obras/{work_id}/{slug}` → ficha HTML (representaciones + JSON-LD)
- `/sitemap.xml` → índice de sitemaps (referencias a `/sitemaps/works-N.xml` y `persons-N.xml`)
- `/sitemaps/{works|persons}-{N}.xml` → páginas de URLs: obras hasta
  `OSAP_SITEMAP_PAGE_SIZE` (por defecto 20.000, tope 50.000) y personas hasta 500
  (límite del API de personas). Cacheadas en memoria y en el cliente.

En **desarrollo** el proxy lo hace `web/public/.htaccess` (regla `[P]` a `127.0.0.1:8001`),
así que tras cambiar el backend **reinicia uvicorn**. En **producción** lo hace la
`location` de `deploy/app.openmusicrepository.com.conf`. El resto de rutas sigue siendo la SPA.

La base canónica se puede cambiar con la variable de entorno `OSAP_PUBLIC_BASE_URL`
(por defecto `https://app.openmusicrepository.com`).

---

## Notas sobre el frontend (UX de la lista de obras)

- Páginas que muestran la lista de obras de una búsqueda:
  - `web/src/pages/CandidatesPage.tsx` (ruta `/candidates`, búsqueda general).
  - `web/src/pages/ComposerPage.tsx` (ruta `/composer`, búsqueda por compositor).
- Comportamiento deseado (implementado): al pulsar una línea se **expande un panel inline**
  en la misma ventana (empuja al resto hacia abajo y cierra cualquier otra abierta), con las
  representations tabuladas (Título / Autor / Acción). **No** debe navegar a `/resolution`
  ni mostrar el aviso "Se han encontrado varias obras compatibles".
- Si se cambia cualquiera de estas páginas: **rebuildar `web/dist`** (paso 2).
