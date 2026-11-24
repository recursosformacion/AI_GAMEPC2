# Matriz mínima de autenticación entre servicios OSAP

**Estado (2026-11-24):** integración API → Support implementada en código y cubierta por pruebas; la configuración de clientes y el smoke test HTTP de producción deben verificarse por separado. No se ha provisionado aquí ningún cliente ni se ha modificado producción.  
**Alcance:** Auth, API, Storage y Support. Chorus utiliza una integración independiente y queda fuera de esta matriz.

> Esta matriz cubre clientes OAuth M2M emitidos por osap-auth. Noticias y publicidad usan actualmente tokens de servicio estáticos propios (`OSAP_NEWS_API_TOKEN` y `OSAP_ADS_SERVICE_TOKEN`); no deben confundirse con JWT M2M ni reutilizar credenciales de Auth.

## Principios

- `osap-auth` es el emisor central de service tokens OAuth2 `client_credentials`.
- Cada cliente de servicio tiene un `client_id` y un secreto propios; Auth conserva el hash del secreto.
- Cada token se solicita para la audiencia del servicio receptor y solo con los scopes concedidos.
- Los tokens son JWT RS256 de corta duración; los receptores validan firma, issuer, audience, expiración, `token_use=service` y scope.
- No se transmite identidad de usuario en un service token. Si una operación necesita actuar en nombre de una persona, debe conservarse el flujo de usuario/delegación correspondiente.
- Los secretos se provisionan por entorno fuera de Git y nunca se copian entre servicios.

## Matriz de llamadas

| Llamante | Receptor | Identidad / audiencia | Scope | Uso |
|---|---|---|---|---|
| osap-api | osap-storage | Cliente general API; audiencia por defecto `osap-api` | `storage:read` | Consultas y lectura de recursos |
| osap-api | osap-storage | Cliente general API; audiencia por defecto `osap-api` | `storage:write` | Escrituras no administrativas |
| osap-api | osap-storage | Cliente admin de compositores; audiencia `osap-api` | `storage:admin` | Fusión y operaciones administrativas de Storage |
| osap-api | osap-support | Cliente general API; audiencia `osap-support` | `api:read` | Lectura M2M de reconocimientos |
| osap-api | osap-support | Cliente admin dedicado; audiencia `osap-support` | `support:admin` | Listar, conceder y revocar reconocimientos |
| osap-api | osap-auth | Cliente general API; audiencia `osap-auth` | `auth:read_public_names` | Resolver nombres públicos |
| osap-storage | osap-api | Sin token | — | `POST /api/v1/composers/resolve` es una operación pública y de solo lectura |

## Estado de la integración API → Support

La integración administrativa está implementada en OSAP API y Support:

- API solicita un token OAuth2 `client_credentials` con audiencia `osap-support`.
- El cliente dedicado tiene exclusivamente el scope `support:admin`; no se reutiliza el cliente general de API ni el cliente administrativo de Storage.
- Support valida los tokens de servicio con su audiencia de servicio `osap-support` y el scope requerido.
- La validación de tokens de usuario sigue usando la audiencia `osap-api` en `auth_audience`; no debe sustituirse por la audiencia M2M.
- El provisionador de Auth es `scripts/provision_support_admin_client.py`. Por defecto hace dry-run; la aplicación exige confirmar el nombre exacto de la base de datos y bloquea entornos productivos.

La integración se considera **lista en código**, pero no verificada en producción hasta que se confirme el cliente real de Auth, las variables de entorno de API y Support y la ejecución satisfactoria del smoke test HTTP.

## Clientes que deben existir en osap-auth

Los nombres son etiquetas operativas; los `client_id` reales son UUID emitidos por Auth.

| Cliente lógico | Audiencia permitida | Scopes mínimos |
|---|---|---|
| osap-api | `osap-api`, `osap-support`, `osap-auth` | `storage:read`, `storage:write`, `api:read`, `auth:read_public_names` |
| osap-composer-admin-service | `osap-api` | `storage:admin` |
| osap-support-admin-service | `osap-support` | `support:admin` |

La configuración de Auth debe conceder a cada cliente únicamente las audiencias y scopes de su fila. No añadir `support:admin` al cliente general ni `storage:admin` al cliente de Support.

El cliente nuevo `osap-support-admin-service` debe crearse mediante el procedimiento administrativo de provisionamiento de `service_clients` de osap-auth. El secreto se muestra una sola vez; guardar el secreto en el gestor de secretos del entorno y el UUID en la configuración de osap-api. No insertar el secreto en claro en la base de datos ni en Git.

## Configuración de osap-api

La configuración del cliente general y del administrador de Storage se mantiene:

- `OSAP_SERVICE_CLIENT_ID` / `OSAP_SERVICE_CLIENT_SECRET`
- `OSAP_ADMIN_CLIENT_ID` / `OSAP_ADMIN_CLIENT_SECRET`

La administración de Support usa credenciales nuevas e independientes:

- `OSAP_SUPPORT_ADMIN_CLIENT_ID`
- `OSAP_SUPPORT_ADMIN_CLIENT_SECRET`

También pueden declararse en `[service]` de `osap.toml` o en `app_config`, siguiendo la precedencia ya implementada. En producción ambos valores son obligatorios y el identificador debe ser UUID.

## Comprobación conjunta

Ejecutar desde el entorno de desarrollo/integración con servicios conectados:

```powershell
pwsh -File script/verify-auth-m2m.ps1
```

El smoke test comprueba:

- Storage sin token → 401.
- Storage con `storage:read` → 200.
- Storage con `storage:admin` sobre una lectura normal → 403.
- Support admin sin token → 401.
- Support admin con `api:read` → 403.
- Support admin con el cliente dedicado y `support:admin` → 200.
- Lectura M2M de Support, resolución de nombres en Auth y fachada pública de colaboradores.

No considerar completado el despliegue de Storage hasta que la prueba se ejecute contra el entorno integrado con `auth.enabled: true` en Storage. La plantilla de ejemplo mantiene esa protección desactivada en desarrollo.

## Fuera de alcance

- Videos utiliza el token de usuario para `/auth/me` y consulta endpoints públicos de API; no necesita M2M para su funcionalidad actual.
- Chorus tiene su propio consumo de identidad/servicios y requiere una configuración independiente; no se modifica en esta tarea.
- Las integraciones de API con News y Ads siguen usando sus credenciales estáticas actuales. Deben auditarse por separado antes de migrarlas a OAuth M2M.
- No se modifica la configuración ni se ejecutan escrituras en producción.
