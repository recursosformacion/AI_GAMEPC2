# Validación de configuración — OSAP

**Fecha:** 2026-08-20  
**Servicio:** osap-api (extensible a osap-auth y osap-storage)  
**Objetivo:** Garantizar la integridad de `osap.toml` antes del arranque, diferenciando estrictamente entre entornos de producción y desarrollo.

---

## 1. Cómo funciona

El sistema se activa automáticamente al llamar a `load_configuration(service_name="...")`. La detección del entorno se realiza mediante la variable de entorno `OSAP_ENV`:

- **Producción (`OSAP_ENV=production`):** validación estricta. Si falta cualquier sección o campo obligatorio, el servicio no arranca y lanza `ConfigurationError` con un mensaje descriptivo.
- **Desarrollo (`OSAP_ENV=development`, valor por defecto):** validación permisiva. Si faltan secciones o campos, se emiten `ConfigurationWarning` pero el servicio continúa.

---

## 2. Reglas por servicio

```python
_SERVICE_REQUIRED_SECTIONS = {
    "osap-api": {
        "db": ["host", "name", "user", "password"],
        "oidc": ["issuer", "client_id", "redirect_uri", "client_secret"],
    },
    "osap-storage": {
        "db": ["host", "name", "user", "password"],
        "repository": ["provider"],
    },
    "osap-auth": {
        "db": ["host", "name", "user", "password"],
        "jwt": ["private_key_path", "public_key_path", "kid"],
    },
}
```

---

## 3. Validaciones adicionales en producción

- **Defaults inseguros de BD:** si `db.host`, `db.user`, `db.password` o `db.name` coinciden con los valores por defecto de desarrollo (`127.0.0.1`, `osap2027`, `2027osapdb`, `osap-api`) y no hay variables de entorno `OSAP_API_DB_*` definidas, se considera inseguro.
- **Dev auth bypass:** si `dev_auth_bypass = true` en producción, se bloquea el arranque.

---

## 4. Integración en el punto de entrada

En `src/osap/api/platform_app.py`:

```python
from src.osap.bootstrap.configuration import load_configuration

def create_platform_app(
    container: Container | None = None,
    knowledge: KnowledgeStore | None = None,
) -> FastAPI:
    config = load_configuration(service_name="osap-api")
    container = container or wire(Container(), configuration=config)
    ...
```

---

## 5. Ejemplo de uso

### Producción (bloquea si falla)

```bash
OSAP_ENV=production python -m uvicorn --factory src.osap.api.platform_app:create_platform_app --host 127.0.0.1 --port 8001
```

Si `osap.toml` falta la sección `[oidc]`:

```
ConfigurationError: [osap-api] Configuración inválida para producción:
  - Sección obligatoria 'oidc' faltante en osap.toml
```

### Desarrollo (advierte pero continúa)

```bash
# Sin OSAP_ENV (default = development)
python -m uvicorn --factory src.osap.api.platform_app:create_platform_app --host 127.0.0.1 --port 8001
```

Si falta `[oidc]`:

```
ConfigurationWarning: [osap-api] Configuración (dev): Sección recomendada 'oidc' faltante en osap.toml
```

---

## 6. Extensión a otros servicios

Para usar la validación en `osap-auth` o `osap-storage`:

1. Añadir las reglas en `_SERVICE_REQUIRED_SECTIONS` en `src/osap/bootstrap/configuration.py`.
2. Llamar a `load_configuration(service_name="osap-auth")` o `load_configuration(service_name="osap-storage")` en el punto de entrada de cada servicio.

---

## 7. Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `src/osap/bootstrap/configuration.py` | Añadidas `ConfigurationError`, `ConfigurationWarning`, `_SERVICE_REQUIRED_SECTIONS`, `validate_configuration`, `_validate_strict`, `_validate_lenient`. `load_configuration` acepta `service_name` y valida automáticamente. |
| `src/osap/api/platform_app.py` | `create_platform_app` carga y valida la configuración con `service_name="osap-api"` antes de armar el `Container`. |
| `tests/osap/test_configuration_validation.py` | Suite de tests (11 casos) que cubre validación estricta, permisiva, defaults inseguros y dev_auth_bypass. |
