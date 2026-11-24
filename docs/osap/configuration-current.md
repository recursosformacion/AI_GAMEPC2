# Configuración actual de OSAP API

**Estado:** VIGENTE, contrastada con `src/osap/bootstrap/configuration.py` y `osap.production-example.toml`.  
**Revisión:** 2026-11-24.  
**Importante:** el ejemplo versionado es una plantilla vacía; no demuestra los valores efectivos del servidor.

## 1. Ficheros y precedencia

El servicio carga el fichero indicado por `OSAP_CONFIG`; si no se indica, utiliza `osap.toml`. Carga también `.env` desde el directorio de trabajo y, si `OSAP_DOTENV` apunta a otro fichero, lo carga como configuración adicional.

La precedencia efectiva es:

1. Variables de entorno del proceso.
2. Valores cargados desde `.env` / `OSAP_DOTENV` que no hayan sido definidos ya en el entorno.
3. Secciones de `osap.toml`.
4. Valores de la tabla `app_config` de la BD operativa, si la conexión está configurada y puede leerse.
5. Defaults del código.

El fichero TOML **no se limita técnicamente a la conexión de BD**: además de `[db]`, el loader admite secciones `[osap]`, `[oidc]`, `[service]`, `[news]`, `[ads]` y `[chorus]`. El ejemplo de producción mantiene parte de los valores en TOML y permite sobrescribirlos por entorno.

La carga de `app_config` se intenta solo cuando están definidos host, usuario, contraseña y nombre de BD. Se abre en modo de solo lectura. Si no se puede leer, el loader continúa con TOML, entorno y defaults; la validación estricta de producción determina después si falta alguna configuración obligatoria.

## 2. Conexión a la base de datos operativa

La sección `[db]` o sus variables equivalentes define la conexión a la BD de OSAP API:

| TOML | Variable de entorno |
|---|---|
| `[db].host` | `OSAP_API_DB_HOST` |
| `[db].name` | `OSAP_API_DB_NAME` |
| `[db].user` | `OSAP_API_DB_USER` |
| `[db].password` | `OSAP_API_DB_PASSWORD` |
| `[db].port` | `OSAP_API_DB_PORT` |

El puerto por defecto es 3306. No copiar contraseñas reales a documentación, ejemplos, tickets o Git.

## 3. Entorno de ejecución

- `OSAP_DEPLOYMENT` tiene prioridad sobre `OSAP_ENV`.
- Si no se define `OSAP_DEPLOYMENT`, `OSAP_ENV=development` selecciona desarrollo; en otro caso el default es producción.
- `OSAP_DEV_MODE` controla el modo de datos dentro de desarrollo: `0` usa las dependencias locales; `1` conecta al origen real configurado en modo de solo lectura, según el wiring descrito en [dev-environment.md](dev-environment.md).

En producción se aplica validación estricta antes de atender tráfico. En desarrollo se emiten advertencias para los campos ausentes, salvo errores de configuración que impidan arrancar.

## 4. OIDC de usuario

La sección `[oidc]` configura el login de usuario mediante osap-auth:

- `issuer`: endpoint de discovery OIDC.
- `client_id`: cliente OIDC `osap-api`.
- `client_secret`: secreto de ese cliente, fuera de Git.
- `redirect_uri`: callback de API.
- `spa_origin`: origen público de la SPA.
- `scope`: por defecto `openid profile`.
- `jwks_url`, `audience` y `token_issuer`: validación de los access tokens de usuario.

El cliente OIDC de usuario no es un service client M2M. No reutilizar su client ID o secreto para llamadas de servicio.

## 5. Clientes M2M

Las credenciales M2M se registran en osap-auth y se configuran en el entorno de OSAP API. Los client IDs de servicio deben ser UUID y cada cliente debe tener únicamente sus audiencias y scopes autorizados.

| Propósito | Variables |
|---|---|
| Cliente general de API | `OSAP_SERVICE_CLIENT_ID`, `OSAP_SERVICE_CLIENT_SECRET` |
| Operaciones administrativas de Storage | `OSAP_ADMIN_CLIENT_ID`, `OSAP_ADMIN_CLIENT_SECRET` |
| Administración de Support | `OSAP_SUPPORT_ADMIN_CLIENT_ID`, `OSAP_SUPPORT_ADMIN_CLIENT_SECRET` |

El cliente de Support es independiente y usa audiencia `osap-support` y scope `support:admin`. No añadir ese scope al cliente general ni compartir secretos con Storage, Auth o Chorus.

Véase [m2m-service-matrix.md](m2m-service-matrix.md) para las llamadas, audiencias, scopes y comprobaciones.

## 6. Integraciones

La plantilla `osap.production-example.toml` documenta las secciones admitidas para:

- Storage: `storage_base_url`, `storage_web_base`, `storage_db_name`.
- Auth: `auth_token_url`, `auth_base_url`.
- Support: `support_base_url`, `support_web_base`.
- Noticias: `news.base_url`, `news.service_token`, `news.timeout_seconds`.
- Publicidad: `ads.base_url`, `ads.service_token`, `ads.web_base`, `ads.timeout_seconds`.

Los tokens estáticos de News y Ads no son tokens de usuario ni deben exponerse al navegador. No documentar aquí valores reales de producción.

## 7. Validación de producción

Para OSAP API, la validación estricta exige:

- Conexión a la BD operativa.
- Configuración OIDC completa.
- Cliente general M2M y cliente administrativo de Storage.
- Cliente administrativo de Support.
- Integraciones de News y Ads.

Los valores efectivos pueden proceder de entorno, TOML o `app_config`, según el campo y su precedencia. La existencia de una clave en `osap.production-example.toml` no prueba que tenga un valor real ni que el servicio receptor acepte las credenciales.

No ejecutar un cambio de configuración en producción sin identificar primero el proceso y fichero efectivos, proteger una copia previa y comprobar el servicio receptor.

## 8. Archivos de referencia

- `osap.production-example.toml`: plantilla versionada, con secretos vacíos.
- `src/osap/bootstrap/configuration.py`: loader, precedencia, defaults y validación.
- `tests/osap/test_configuration_validation.py`: pruebas de configuración.
- [Entorno de desarrollo](dev-environment.md): hosts, puertos, Apache, uvicorn y modo de solo lectura.
