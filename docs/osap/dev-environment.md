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
   ├─ /obra/*, /compositor/* → osap-api (HTML SEO server-rendered, `api/http/seo.py`)
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

Todos apuntan a `127.0.0.1`.

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

---

## Capa pública SEO (/obra y /compositor)

Las URLs indexables de entidad las sirve **osap-api** con HTML server-rendered
(`src/osap/api/http/seo.py` + plantillas en `src/osap/api/templates/`). No forman parte de
`/api` y no las renderiza la SPA:

- `/compositor/{person_id}` → 301 a `/compositor/{person_id}/{slug}`
- `/compositor/{person_id}/{slug}` → ficha HTML (biografía + obras + JSON-LD)
- `/obra/{work_id}` → 301 a `/obra/{work_id}/{slug}`
- `/obra/{work_id}/{slug}` → ficha HTML (recursos + JSON-LD)
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
