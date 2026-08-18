# AGENTS.md — OSAP (osap-api)

Instrucciones para agentes (Kilo y similares) que trabajen en este repositorio.

## ⚠️ LEER ANTES DE TOCAR EL FRONTEND O LEVANTAR SERVICIOS

El entorno de desarrollo **no usa `vite dev`**. La app se sirve con **Apache (XAMPP)**:
- `http://osap-app` → VirtualHost Apache que sirve el build estático **`web/dist`**
  y proxya `/api` → uvicorn **127.0.0.1:8001**.
- Flujo completo, hosts, comandos y errores a evitar: **`docs/osap/dev-environment.md`**
  (abre este fichero y síguelo).

### Reglas rápidas
1. **Frontend** (`web/src/...`): tras cada cambio, **rebuildar**:
   ```powershell
   cd web
   .\node_modules\.bin\tsc.cmd --noEmit
   node node_modules/vite/bin/vite.js build
   ```
   Apache sirve `web/dist` al instante; recargar `http://osap-app` con cache limpia.
   No usar `npm run dev` (falla por el hook de pnpm/esbuild).
2. **Backend** (`src/osap/...`): tras cada cambio, **reiniciar uvicorn** en 8001:
   ```powershell
   python -m uvicorn --factory src.osap.api.platform_app:create_platform_app --host 127.0.0.1 --port 8001
   ```
3. **Verificar** el proxy: `http://osap-app/api/v1/system/health`.

## Verificaciones estándar (backend)
```powershell
python -m ruff check src/osap tests/osap
python -m mypy src/osap
python -m pytest tests/osap -q
```
Frontend: `tsc --noEmit` y `vitest run` en `web/`.

## Arquitectura de proveedores (v1.3)
- Capa declarativa por YAML en `providers/{omr,imslp,openscore}/` (provider/endpoints/
  mapping/resources.yaml) + `RemoteCatalogProvider` genérico.
- Ver `docs/osap/providers-layer.md` y `docs/osap/README.md`.

## Regla permanente: documentación de scripts
- Todo script que se quede en `script/` (o `scripts/` en osap-storage) y sea lanzable
  debe llevar un **resumen corto al principio** (docstring en Python, comentario en
  PowerShell) y estar **documentado en `docs/osap/scripts.md`** (propósito + uso).
- Aplica a los scripts existentes y a los nuevos.

