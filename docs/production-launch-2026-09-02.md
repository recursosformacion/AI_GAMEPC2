# Lanzamiento a producción — 2026-09-02 (registro operativo)

> Documento vivo del despliegue: alcance, salvaguardas, resultados y **pendientes de
> seguridad** que quedan anotados para corregir después (no bloquean el lanzamiento).

## 1. Alcance aprobado

- Subir a producción y verificar: **osap-auth**, **osap-storage**, **osap-api** (en ese orden).
- Chorus: **fuera de esta ronda** (sin release script ni servicio en el servidor).
- Salvaguardas: registrar pendientes → push de commit pendiente de storage → prechecks
  de solo lectura → ejecutar releases → verificación de health.

## 2. Resultados del despliegue

| Servicio | Release | Resultado | Health |
|---|---|---|---|
| osap-auth | `scripts/release.ps1` | ✅ completado (79 tests; web build 60 módulos) | `{"status":"ok"}` (8200) |
| osap-storage | `release.ps1` | ✅ completado (226 tests; migraciones) | `{"status":"ok",...,"entries":254035}` (8000) |
| osap-api | `script/deploy.ps1` | ✅ completado (vite build 113 módulos; RESTART_DONE) | público `https://app.openmusicrepository.com/api/v1/system/health` → 200 |

### Notas del despliegue (2026-09-02)
- **502 transitorio en osap-api**: el check de salud del deploy.ps1 corrió justo tras el
  restart (uvicorn aún arrancando). El servicio quedó `active` y health 200; no fue fallo real.
- **Cloudflare 403**: curl sin User-Agent de navegador es bloqueado por el WAF en el dominio
  público; con UA de navegador los endpoints públicos responden 200
  (`providers`, `repository-sources`, `search-model`).
- **Fix de calidad requerido por el release de osap-auth** (preexistentes, ahora corregidos):
  - `api/main.py`: imports sin usar (`os`,`Path`) y `Any` sin importar (F821).
  - `infrastructure/cli.py`: `os` sin usar, E501 y `data` sin anotación (mypy).
  - `tests/test_config_validation.py`: F401/I001/E501.
  - `pyproject.toml` (osap-auth): extra `dev` referenciaba osap-api por ruta local
    `file:///F:/DiscoD/...` que rompía `pip install -e .` en el servidor → eliminada la
    referencia directa (osap-api se instala aparte cuando se necesita).
  - `scripts/release.ps1` (osap-auth): paso 4 ahora instala `-e .` (runtime) en el
    servidor en lugar de `-e '.[dev]'`.
- **Aviso nginx (auth release)**: `conflicting server name "app.openmusicrepository.com"`
  ignorado al aprovisionar el sitio de auth. No afectó a la salud; verificar que el sitio
  real de la SPA es el previsto antes del siguiente despliegue de la app.
- **osap-support**: NO desplegado (esqueleto Fase 1, sin release script).
- **Chorus**: fuera de esta ronda (sin servicio en el servidor; pendiente de decisión).

## 3. PENDIENTES DE SEGURIDAD (no bloqueantes para este lanzamiento)

Correcciones de contraseñas / API keys / secretos detectadas en la auditoría de
2026-09-02 y **dejadas anotadas para resolver en un incremento posterior**:

### 3.1 osap-auth — separar y rotar claves JWT por entorno
- `config.yaml` (dev) comparte la **misma `jwt_private_key`/`jwt_public_key`** que
  `config.production.yaml` (prod). `client_secret` y `social_state_secret` sí difieren.
- Acción: generar claves JWT distintas para prod y dev, actualizar ambas configs y
  rotar (invalidando tokens antiguos con margen controlado).

### 3.2 Passwords de BD compartidas
- Password prod **`osap2027`** compartida entre osap-api / osap-auth / osap-storage y
  presente en copias sueltas (`osap-support/osap*.toml`, `Chorus/osap*.toml`).
- Password dev **`2027osapdb`** compartida igualmente.
- Acción: credenciales distintas por servicio y por entorno + gestor de secretos.

### 3.3 Secretos en historial git (osap-api y osap-support)
- osap-api: historial git (ya pusheado a GitHub) contiene la password de BD
  (dev y prod) y el `client_secret` de dev en commits antiguos previos a la limpieza.
- osap-support: `osapx.toml` y `osap.productionx.toml` (copias de config de osap-api
  con credenciales) están **trackeados** en el repo.
- Acción: rotar credenciales afectadas y/o reescribir historial; eliminar y sacar del
  historial los `osapx.toml` de osap-support; borrar la carpeta `Chorus/` residual
  (o gitignorarla y guardar solo en gestor).

### 3.4 osap-storage — API keys de objetos/authority
- `config.production.yaml` contiene credenciales reales Cloudflare R2
  (`access_key`/`secret_key`) y token Metabrainz. El fichero está gitignoreado y nunca
  estuvo en git, pero rota periódicamente y verifica que no existan en historial ni en
  copias sueltas (los `osap*.toml` de osap-support/Chorus NO deben replicarlas).

### 3.5 Verificación global de secretos
- Ejecutar secret-scanning (p. ej. gitleaks/trufflehog) sobre el historial de
  `AI_GAMEPC2` (osap-api), `AI_osap-auth`, `AI_osap-storage`, `AI_osap-support` antes
  de dar el lanzamiento por cerrado.

## 4. Notas operativas

- Este despliegue incluye el código actual del backend (incluye el paquete `chorus` en
  `src/` y los cambios de wiring de proveedores). El API en producción registra
  proveedores con `wired=True` según la BD operativa `osap_api` (precheck §5).
- El frontend de osap-app (`web/dist`) se reconstruye y despliega con `deploy.ps1`.
