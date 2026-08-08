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

## Notas sobre el frontend (UX de la lista de obras)

- Páginas que muestran la lista de obras de una búsqueda:
  - `web/src/pages/CandidatesPage.tsx` (ruta `/candidates`, búsqueda general).
  - `web/src/pages/ComposerPage.tsx` (ruta `/composer`, búsqueda por compositor).
- Comportamiento deseado (implementado): al pulsar una línea se **expande un panel inline**
  en la misma ventana (empuja al resto hacia abajo y cierra cualquier otra abierta), con las
  representations tabuladas (Título / Autor / Acción). **No** debe navegar a `/resolution`
  ni mostrar el aviso "Se han encontrado varias obras compatibles".
- Si se cambia cualquiera de estas páginas: **rebuildar `web/dist`** (paso 2).
