# OSAP — Configuración centralizada en BD operativa (v1)

La configuración de osap-api ya **no vive en ficheros**: se centraliza en la **BD operativa**
(tabla `app_config`). El fichero `osap.toml` solo guarda la **conexión a la BD**.

---

## 1. `osap.toml` — solo conexión

```toml
[db]
host = "127.0.0.1"
name = "osap_api"
user = "osap"
password = "osap2027"
```

Nada más. No contiene rutas, credenciales de servicio, ni `dev_mode`.

- **Producción**: usa este `osap.toml` (usuario `osap`, BD `osap_api`; MySQL ya concedió
  `ALL PRIVILEGES ON osap_api.*`).
- **Desarrollo local**: sobreescribe la conexión por variable de entorno (env > osap.toml):
  ```
  OSAP_API_DB_USER=osap2027 OSAP_API_DB_PASSWORD=2027osapdb OSAP_API_DB_NAME=osap-api OSAP_DEPLOYMENT=dev
  ```


## 2. Precedencia de la configuración

```
variable de entorno (OSAP_*)  >  BD (app_config)  >  defaults en código
```

- `osap.toml` `[db]` define la conexión (o env `OSAP_API_DB_*`).
- La BD operativa (tabla `app_config`, clave-valor) guarda el resto de campos.
- Cualquier campo se puede sobreescribir con variable de entorno.

## 3. Entorno y rutas: `deployment` + `dev_mode`

| `deployment` | `dev_mode` | Rutas | Escritura |
|---|---|---|---|
| `prod` (default) | – | reales (storage/auth prod) | sí |
| `dev` | `0` | locales (127.0.0.1:8000 / 8200) | sí |
| `dev` | `1` | reales (storage/auth prod) | **solo lectura** (aviso) |

- `deployment` (env `OSAP_DEPLOYMENT`, default `prod`): qué despliegue es.
- `dev_mode` (env `OSAP_DEV_MODE` / BD, 0 o 1): decide las rutas cuando `deployment=dev`.
- La barra de aviso de la web se muestra **solo** en `dev` + `dev_mode=1` (storage real, solo lectura).

## 4. BD operativa (MySQL)

- Conexión en `[db]`. Tablas: `source_suggestions`, `providers`, `app_config`.
- Si MySQL no está disponible (usuario/BD sin crear), degrada a **memoria** (aviso en log) para
  no tumbar el servicio.

## 5. Endpoints operativos (admin)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/admin/op/providers` | lista proveedores dinámicos |
| POST | `/api/v1/admin/op/providers` | registra/actualiza un proveedor |
| POST | `/api/v1/admin/op/providers/{id}/wire` | activa/desactiva (wired) |
| GET | `/api/v1/admin/op/config` | lee config operativa |
| PUT | `/api/v1/admin/op/config` | persiste una clave (p. ej. `dev_mode`) |

Para cambiar `dev_mode`:
```
PUT /api/v1/admin/op/config   {"key":"dev_mode","value":"1"}
```
(efecto tras reiniciar osap-api) o directamente en la tabla `app_config`.

## 6. Pendiente en producción

El MySQL de prod debe tener creados el usuario y la BD de osap-api:

```sql
CREATE DATABASE IF NOT EXISTS `osap-api`;
CREATE USER IF NOT EXISTS 'osap2027'@'localhost' IDENTIFIED BY '2027osapdb';
CREATE USER IF NOT EXISTS 'osap2027'@'127.0.0.1' IDENTIFIED BY '2027osapdb';
GRANT ALL PRIVILEGES ON `osap-api`.* TO 'osap2027'@'localhost';
GRANT ALL PRIVILEGES ON `osap-api`.* TO 'osap2027'@'127.0.0.1';
FLUSH PRIVILEGES;
```

Hasta entonces prod usa el fallback a memoria (funciona; las sugerencias no persisten entre reinicios).
