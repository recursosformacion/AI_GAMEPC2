# Verificación 4.1 — BLOQUEADA POR DESPLIEGUE

Estado: **ni fallo ni cerrada**. La funcionalidad de 4.1 (cuota de descargas OMR, gateo de
endpoints, protección de `/api/download` en storage y panel admin) está **en local, sin
commit ni despliegue**. Producción sigue en **4.0**, por lo que la verificación E2E no
procede todavía.

## Baseline pre-despliegue (producción = 4.0)

| Comprobación | Resultado |
|---|---|
| `storage.openmusicrepository.com/api/download/1` (sin credenciales) | **302** |
| Descarga OMR vía osap-api | **200** |
| `osap_api.download_usage` | **tabla inexistente** |
| `osap_api.download_quota_daily` | **tabla inexistente** |

Conclusión: **4.1 no está desplegada**. El 302 confirma que el bypass de storage sigue
abierto en producción (comportamiento esperado: el cierre va en 4.1).

## Circuito a ejecutar cuando se autorice el despliegue de 4.1

1. **Mantenimiento ON** (prod): `web/scripts/maintenance.ps1 -On -RemoteOnly`.
2. **Backup**: `script/predeploy_backup.ps1` (4 BBDD + 5 programas).
3. **Desplegar los 5 programas**: `script/deploy_all.ps1` (SPA + osap-api/auth/storage/support,
   incluido el admin de storage).
4. **Tablas de cuota**: se crean al arrancar osap-api (`download_plans` sembrado 10/100/1000,
   `user_quota_overrides`, `download_quota_daily`, `download_usage`).
5. **Comprobar arranque**: health 8000/8001/8200/8300 y proxy.
6. **Verificación E2E**, en este orden:
   1. `storage/api/download/1` sin credenciales → **401**.
   2. Descarga equivalente pasando por osap-api → **200** (osap-api obtiene y propaga
      `storage:read`).
   3. Usuario **temporal** de prueba (creado en osap-auth, solo para esta prueba):
      - descargas **1–100 → 200**;
      - descarga **101 → 429** (`QUOTA_EXCEEDED`);
      - comprobar contador (`download_quota_daily`) y `download_usage`.
   4. **Limpieza**: borrar `download_usage`/`download_quota_daily` generados y **eliminar el
      usuario temporal**.
7. **Mantenimiento OFF** y comprobación pública final (sin `503` residual).

Sin cambios de configuración local. Producción solo se toca con el usuario temporal
necesario para la prueba.
