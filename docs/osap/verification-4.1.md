# Verificación 4.1 — CERRADA Y DESPLEGADA — v4.1.0

Estado: **4.1 — CERRADA Y DESPLEGADA — v4.1.0**. Verificada sobre **producción** con el
circuito real (sin mocks ni auth local provisional).

## Baseline pre-despliegue (producción = 4.0)

| Comprobación | Resultado |
|---|---|
| `storage.openmusicrepository.com/api/download/1` (sin credenciales) | **302** |
| Descarga OMR vía osap-api | **200** |
| `osap_api.download_usage` | **tabla inexistente** |
| `osap_api.download_quota_daily` | **tabla inexistente** |

## Circuito ejecutado (producción)

mantenimiento ON → backup → deploy 5 programas → creación de tablas de cuota → arranque →
E2E → limpieza → mantenimiento OFF → comprobación pública.

## Resultado E2E (post-despliegue)

| Caso | Evidencia |
|---|---|
| **1. Storage directo sin credenciales** | `storage/api/download/1` → **401** ✅ (antes 302) |
| **2. Descarga OMR vía osap-api** | `osap-api download` → **200**, con cuota registrada (`ip:127.0.0.1 used=1` y fila en `download_usage`) → osap-api obtiene y propaga `storage:read` ✅ |
| **3. Usuario registrado** | req **1/99/100 → 200**, req **101 → 429** (`QUOTA_EXCEEDED`); contador `u:<user>=100`; 100 filas de `download_usage` ✅ |

- Tablas creadas al arrancar: `download_plans` (visitor 10 / registered 100 / donor 1000),
  `user_quota_overrides`, `download_quota_daily`, `download_usage`.
- **Limpieza**: usuario temporal `c02139c2…` eliminado (y `tokens`/`sessions`/
  `authorization_codes`); `download_quota_daily` = 0; `download_usage` = 0.
- **Mantenimiento OFF**: `app /` → 200, `app /viewer` → 200. Servicios 8000/8001/8200 → 200
  (support por `/support-api/health` → 200).
- **Backup previo**: `/home/ocw/backups/20260927-091321` (4 BBDD + 5 programas).
- Storage con `auth_enabled: true`; **sin cambios de configuración**.

## Release v4.1.0 (tags → commits desplegados)

| repo | `main` | tag `v4.1.0` |
|---|---|---|
| osap-api | `efa2074` | `efa2074` |
| osap-storage | `a19cf1e` | `a19cf1e` |
| osap-auth | `c66c311` | `c66c311` |
| osap-support | `36e4508` | `36e4508` |

Nota: el contenido desplegado es el mismo código que estos commits; la única diferencia es
la cadena de versión (`pyproject`/`package.json` → `4.1.0`), que no afecta al comportamiento.

## Alcance de 4.1

- Cuota de descargas OMR: planes `visitor 10 / registered 100 / donor 1000` (donor
  preparado, aún desacoplado de osap-support), excepción por usuario con vigencia
  (`user_quota_overrides`), consumo atómico y auditoría (`download_usage`), 429
  `QUOTA_EXCEEDED`.
- Gateo en `download_representation` y `/api/v1/omr/download`.
- Cierre del bypass de storage: `/api/download/{id}` exige service token `storage:read`.
- Panel admin de **Cuotas** y **Estadísticas**.
- Scripts: `script/predeploy_backup.ps1`, `script/deploy_all.ps1` (incluye admin de storage).
