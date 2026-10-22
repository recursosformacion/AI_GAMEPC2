# Ficha de PROD — SSR de páginas públicas (2026-10-21)

Documento de preparación. **No se ha desplegado nada.** Las fechas y la versión se dejan
en blanco a propósito para rellenarlas en la ventana de despliegue.

## 1. Qué se despliega

- SPA React (`web/dist`) con los cambios de UI: ficha de compositor en fieldsets, «Ver» /
  «Descargar», bloque de «buscar mejores» con ≥2 ficheros accesibles, correcciones solo con
  sesión, `notranslate` en iniciales.
- HTML SSR React (`web/dist-ssr` + `web/ssr/server.mjs`) para:
  - `/composers`
  - `/composers/<id>/<slug>`
  - `/obras/<id>/<slug>`
- API: nuevo `GET /api/v1/composers/{id}/index-works` (solo lectura).
- nginx: `/composers` y `/obras/` pasan de `osap_api` (Jinja) a `osap_ssr` (Node 3000).
  Las URLs antiguas `/obra`, `/compositor`, `/representacion` siguen en `osap_api` (301).
- No hay cambios de esquema ni escrituras en la BD de producción.

## 2. Ficha de PROD (rellenar solo lo que falte)

| Campo | Valor |
|---|---|
| Host SSH | `RemoteIA` |
| Dominio | `https://app.openmusicrepository.com` |
| Usuario del servicio | `ocw` |
| Backend OSAP | `/home/ocw/openmusicrepository.com/osap-api` |
| Web del backend | `/home/ocw/openmusicrepository.com/osap-api/web` |
| Plantilla SSR | `OSAP_WEB_DIST=/home/ocw/openmusicrepository.com/app` |
| SPA | `/home/ocw/openmusicrepository.com/app` |
| API | `127.0.0.1:8001` (`osap-api.service`) |
| SSR | `127.0.0.1:3000` (`osap-ssr.service`) |
| Node | 22.x (`/usr/bin/node`) |
| nginx | `/etc/nginx/sites-enabled/app.openmusicrepository.com.conf` |
| Caché | Node 60 s + stale 600 s; nginx opcional |
| Versión a desplegar | *(pendiente de clasificar y etiquetar)* |
| Fecha de ventana | 2026-10-22, 12:00–13:00 (Europe/Madrid) |
| Responsable | *(pendiente)* |

## 3. Prerrequisitos (una vez)

1. Node 22 en el VPS (no está instalado hoy):

   ```bash
   curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
   sudo apt-get install -y nodejs
   node --version   # v22.x
   ```

2. Dependencias de ejecución del SSR. El bundle externaliza React/Zustand/Router; en
   `.../osap-api/web` deben existir:

   ```bash
   cd /home/ocw/openmusicrepository.com/osap-api/web
   npm ci --omit=dev
   ```

   `package.json` y `package-lock.json` se despliegan junto al código.

3. Servicio systemd: copiar `deploy/osap-ssr.service` a
   `/etc/systemd/system/osap-ssr.service` y `sudo systemctl daemon-reload`.

4. (Opcional, fase 2) caché nginx. Añadir en `http {}`:

   ```nginx
   proxy_cache_path /var/cache/nginx/osap_ssr levels=1:2 keys_zone=osap_ssr:10m
                    max_size=512m inactive=2h use_temp_path=off;
   ```

   y en las `location` del SSR:

   ```nginx
   proxy_cache osap_ssr;
   proxy_cache_key "$scheme$host$request_uri$cookie_osap_lang$cookie_osap_theme";
   proxy_cache_valid 200 60s;
   proxy_cache_use_stale updating error timeout http_500 http_502 http_503 http_504;
   add_header X-Cache-Status $upstream_cache_status always;
   ```

## 4. Build local (orden importante)

El build SSR puede vaciar `dist/`; por eso el cliente se compila **al final**:

```powershell
cd D:\Proyectos\AI_OSAP\osap-api\web
.\node_modules\.bin\tsc.cmd --noEmit
npm run build:ssr
npm run build
Test-Path dist\index.html
Test-Path dist-ssr\entry-server.js
```

`npm run build:all` hace lo mismo (SSR y después cliente).

## 5. Despliegue

1. **Backup previo** (BD/config actual): `script/predeploy_backup.ps1` (según su ayuda).
2. Empaquetar y subir:
   - `web/dist/*` → `/home/ocw/openmusicrepository.com/app/`
   - `web/dist-ssr/*`, `web/ssr/`, `web/package.json`, `web/package-lock.json`
     → `/home/ocw/openmusicrepository.com/osap-api/web/`

   El servicio usa `OSAP_WEB_DIST=/home/ocw/openmusicrepository.com/app`: la plantilla
   `index.html` se lee de la SPA publicada, no de `web/dist`.
   - `deploy/osap-ssr.service` → `/tmp/osap-ssr.service`
3. En el servidor:

   ```bash
   cd /home/ocw/openmusicrepository.com/osap-api/web
   npm ci --omit=dev
   sudo cp /tmp/osap-ssr.service /etc/systemd/system/osap-ssr.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now osap-ssr
   curl -fsS http://127.0.0.1:3000/health   # ok
   ```

4. nginx (solo en la ventana). Sustituir las location actuales de `/composers` y
   `/obras/` por:

   ```nginx
   upstream osap_ssr {
       server 127.0.0.1:3000;
       keepalive 16;
   }

   location = /composers {
       proxy_pass http://osap_ssr;
       proxy_http_version 1.1;
       proxy_set_header Connection "";
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       proxy_read_timeout 10s;
   }

   location ~ ^/(composers|obras)/ {
       proxy_pass http://osap_ssr;
       proxy_http_version 1.1;
       proxy_set_header Connection "";
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       proxy_read_timeout 10s;
   }

   # Las URLs antiguas siguen en la API (301):
   location ~ ^/(obra|compositor|representacion)/ {
       proxy_pass http://osap_api;
       proxy_http_version 1.1;
       proxy_set_header Host $host;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
   }
   ```

   Mantener `/amigos/...` en `osap_api`. Después:

   ```bash
   sudo nginx -t && sudo nginx -s reload
   ```

5. No reiniciar `osap-api` si no se despliega el backend; si se despliega, usar
   `script/deploy.ps1` o `script/deploy_all.ps1` y comprobar salud.

## 6. Verificación (obligatoria antes de abrir)

- [ ] `curl -fsS http://127.0.0.1:3000/health` → `ok`.
- [ ] `curl -sS -D- https://app.openmusicrepository.com/composers` → 200, `text/html`,
      `<html lang="es">`, título, banner «Producción · solo lectura», filas con datos.
- [ ] `curl -sS https://app.../composers | grep -o 'href="/obras/index-[^"]*"'` → ids
      `index-*`, **nunca** `work-<uuid>`.
- [ ] `curl -sS https://app.../obras/index-532342` → 200, pestañas Resumen/Páginas/
      Evidencia/Proveedores.
- [ ] Ficha de compositor: «Identidad y nombre» y «Biografía» como `fieldset`; Visible en
      identidad; fechas y nacionalidad en Biografía; sin «Años» ni «Publicación».
- [ ] «Buscar mejores representaciones» no aparece con 0/1 ficheros accesibles.
- [ ] «Ver» y «Descargar» (no «Versión»/«Descripción»).
- [ ] Anónimo: no aparece «Proponer corrección»; `/corrections` pide sesión para
      correcciones (contacto abierto).
- [ ] Navegador real: consola sin `Hydration failed` ni `did not match`; el HTML inicial
      ya trae los datos (no spinner).
- [ ] Login OIDC, cambio de idioma y tema sin recargar en blanco.
- [ ] Caché: segunda petición a `/composers` con `Cache-Control: public, s-maxage=60…`
      (y `X-Cache-Status: HIT` si se activó nginx).
- [ ] Visor/descarga de una obra **OMR** desde producción (Cloudflare): comprobar que el
      fichero se sirve. En local el fallo actual apunta al token `storage:read`/resolución
      del fichero, no a que el binario no exista.

## 7. Rollback

Sin migraciones ni cambios de datos: el rollback es de rutas.

1. `sudo systemctl disable --now osap-ssr` (o dejarlo, no molesta).
2. Restaurar la versión anterior del vhost (con `/composers` y `/obras/` hacia
   `osap_api`).
3. `sudo nginx -t && sudo nginx -s reload`.
4. Comprobar `/composers` y `/obras/<id>` (vuelven a Jinja).
5. La SPA sigue igual; si el problema es del bundle, restaurar el `dist` anterior.

## 8. Riesgos y pendientes

- **Hidratación**: no verificada aún en navegador real; es el riesgo principal.
- **Node**: runtime nuevo en producción; instalar y fijar versión.
- **Dependencias SSR**: `npm ci --omit=dev` en `web` (React/Router/Zustand). Validar que
  el bundle no pida nada de `devDependencies`.
- **OMR/Cloudflare**: corregir la nota anterior: OMR siempre funcionó; el 401 actual es de
  service token/storage, no de binarios ausentes. Verificar con el token de servicio.
- **Caché**: la de Node ya funciona; la de nginx es opcional y hay que medir aciertos.
- **Versionado**: clasificar (previsiblemente B), alinear los cuatro `pyproject.toml` +
  `web/package.json`, `script/check-versions.ps1` y etiquetar antes de desplegar.
- **Vista previa**: probar con `?preview=<TOKEN>` si se activa mantenimiento.

## 9. Historial de actualizaciones (rellenar al desplegar)

| Fecha | Versión | Cambio | Resultado | Responsable |
|---|---|---|---|---|
|  |  |  |  |  |
|  |  |  |  |  |
