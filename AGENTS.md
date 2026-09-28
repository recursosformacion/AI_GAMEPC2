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

## Regla permanente: versionado A.B.C (obligatoria)
Detalle en `docs/osap/versioning.md`. Antes de commitear código, clasifica el cambio y
respétalo; si no encaja en la regla, no lo commitees.
- **A** — orientación (MAJOR): rompe contrato/esquema. Exige **punto de control** (tag +
  rama de mantenimiento de la línea anterior) antes de empezar. Afecta a todos los programas.
- **B** — mejora (MINOR): capacidad nueva **compatible**, puede tocar ≥1 programa.
- **C** — corrección (PATCH): solo corrige un defecto, **exactamente un programa**, sin
  cambiar contratos ni esquema, y con prueba. Si toca dos programas → es B; si rompe
  contrato → es A.
- Un número para todo el conjunto: al preparar entrega se alinean los cuatro `pyproject.toml`
  + `osap-api/web/package.json`, se verifica con `script/check-versions.ps1` y se etiqueta
  `vX.Y.Z` en los cuatro repos. Nunca versionar un programa en solitario; nunca reutilizar
  un número; nunca empujar tags/releases sin autorización explícita.
- Toda entrega añade su entrada (clasificación + alcance + evidencia) al historial de
  `docs/osap/versioning.md`.

## Dependencias nuevas en producción
Si un cambio añade una dependencia de Python, hay que instalarla en el venv de producción
(el deploy solo instala lo que explicita `script/deploy.ps1`). Comprobar su presencia con
`ssh RemoteIA ".../.venv/bin/pip show <paquete>"` **antes** de desplegar, para no tumbar el
servicio por un `ImportError` en el arranque.


