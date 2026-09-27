# Verificación 4.2 — Funnel (E2E en producción)

Estado: **CERRADA — v4.2.0** (desplegada en producción). No se tocaron auth, cuotas ni el
circuito de descarga.

## Baseline pre-despliegue (producción = 4.1 / `v4.1.0`)

| Comprobación | Resultado |
|---|---|
| `osap_api.funnel_events` | **tabla inexistente** |
| `download_quota_daily` / `download_usage` / `user_quota_overrides` | **0 filas** |
| `osap-storage` `auth.enabled` | `true` |

## Circuito ejecutado (producción)

mantenimiento ON → backup → `deploy_all` → cableado M2M → E2E (usuario temporal) →
limpieza → mantenimiento OFF → comprobación pública.

- Desplegado: `osap-api 063b05f`, `osap-support 256c154`, `osap-storage a19cf1e`,
  `osap-auth c66c311` (+ correcciones del E2E sin commitear, ver abajo).
- Backups: `/home/ocw/backups/20260927-120254`, `/home/ocw/backups/20260927-122824`.
- `funnel_events` se crea al arrancar (`CREATE TABLE IF NOT EXISTS`).

## Resultado E2E

| Paso | Evidencia |
|---|---|
| **A** baseline | invariantes capturados (arriba) |
| **B** anónimo | 10×200 → **429**; `ip:127.0.0.1 used=10`; `limit_reached` **S1** |
| **C** registro | `POST /api/v1/auth/register` → `registered` **S2** (user_id real) |
| **D** usuario | 100×200 → **429**; `u:<uid> used=100`; `limit_reached` **S3** (`limit:100`) |
| **E** membresía activa → reconciliar | `applied=1`; override **1000** `[2026-09-01, 2026-12-01]`; `membership_activated`+`promotion_applied` **S4**; 2ª pasada `noop` (idempotente) |
| **F** efecto real | descarga tras agotar 100 → **200**; `used=101` |
| **G** revocación admin | `POST …/revoke` → 200 `revoked:true`; override borrado; `promotion_reverted` **S3** con motivo+periodo; reconciliar mismo periodo → `revoked`, **no resucita** |
| **H** renovación | nuevo periodo → `applied=1`; override `[2027-01-01, 2027-06-01]`; 2º `promotion_applied` |
| **I** caducidad | `lapsed=1`; override retirado; `membership_lapsed` **S2** (sin `promotion_reverted`) |

## Hallazgos y correcciones

1. **`service_audience` no se aplicaba (bug de cableado).** `[identity] service_audience`
   no estaba en el mapa TOML→env de `osap-support/infrastructure/config.py`, así que el
   validador M2M caía al `audience` de usuario (`osap-api`): un token con `aud=osap-support`
   daba 401. **Corregido**: se mapea `service_audience` (env `OSAP_SUPPORT_AUTH_SERVICE_AUDIENCE`)
   + tests. Además, `ClientCredentialsServiceTokenProvider` (osap-api) acepta `audience`; el
   reconciliador lo pide con `--support-audience` (por defecto `osap-support`). Verificado:
   `aud=osap-support` → 200, `aud=osap-api` → 401.
2. **Reconciliación automática ausente.** `deploy_all.ps1` no subía `script/` y no había
   programación. **Corregido**: `script/` se despliega y se añaden las units
   `deploy/osap-reconcile-membership.{service,timer}` (systemd, cada 15 min). Ejecución real
   verificada (`applied=1`). Con support inalcanzable → `skipped=1` y el override **no** se
   retira (ni se emite `membership_lapsed`).
3. `registered` solo se emite en `POST /api/v1/auth/register` (registro confirmado por
   osap-auth). Es el contrato implementado; sin cambios.

## Cableado M2M y credenciales

- Service client `osap-api` en osap-auth (`scope api:read`, `aud_allow [osap-support]`) y
  entrada `[m2m]` en osap-support. El id/secret que se usó durante el E2E se **rotó** al
  terminar; el cliente actual es `243ae126-…` y el secreto vive en
  `/home/ocw/openmusicrepository.com/osap-api/osap-reconcile.env` (`600`, fuera del repo).

## Limpieza e invariantes

- Borrados: usuarios temporales (auth) + tokens/sessions/codes, `memberships`/`support_members`,
  overrides, `download_quota_daily`, `download_usage` y `funnel_events` de prueba. Post-limpieza:
  **todo 0**; planes intactos (`visitor 10 / registered 100 / donor 1000`).
- `auth_enabled=true`; público `app/`, `/viewer`, `/api/v1/system/health`, auth, support,
  storage → **200**.

## Release v4.2.0

| repo | `main` / tag `v4.2.0` |
|---|---|
| osap-api | `d692b68` (funnel + fix `service_audience` + Colaboradores → registro + timer) |
| osap-support | `71059c4` (`service_audience` mapeado + tests) |
| osap-storage | `af27242` (versión coordinada) |
| osap-auth | `5af002b` (versión coordinada) |

Además: los 3 botones no-Apoyar de **Colaboradores** enlazan a la pantalla de registro de
osap-auth (`/auth/register`); "Apoyar a OSAP" sigue en `/support`.

## Notas / supuestos

- El emisor OMR (externo) ya pide `aud=osap-support` (su cliente tiene
  `allowed_audiences=["osap-support"]`); al fijar `service_audience` no cambia su contrato.
- Un cliente de servicio borrado responde **500** (en vez de 400 `invalid_client`) al pedir
  token: comportamiento preexistente de osap-auth, no bloqueante (no se emite token).
- Credenciales externas pegadas en sesiones previas (Gemini/OpenRouter) quedan **pendientes
  de rotación por el usuario**; no forman parte de OSAP.
