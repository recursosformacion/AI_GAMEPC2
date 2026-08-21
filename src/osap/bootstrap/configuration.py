import os
import tomllib
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigurationError(Exception):
    """Error de configuración que impide el arranque del servicio."""

    def __init__(self, service: str, message: str) -> None:
        super().__init__(f"[{service}] {message}")
        self.service = service
        self.message = message


class ConfigurationWarning(UserWarning):
    """Warning de configuración en desarrollo (no bloquea el arranque)."""
    pass


@dataclass(frozen=True)
class Configuration:
    """Configuración de osap-api.

    Los valores viven centralizados en la BD operativa (`app_config`), con defaults en
    código y override por variable de entorno. El fichero osap.toml SOLO contiene la
    conexión a la BD ([db]). `deployment` (prod/dev) y `dev_mode` deciden las rutas.
    """

    deployment: str = "development"  # "prod" | "development" (default)
    dev_mode: int = 0  # 0 = local, 1 = real (solo lectura) — solo en dev
    confidence_threshold: float = 0.8
    max_processing_time: float = 300.0
    default_quality_level: str = "full_notation"
    default_output_format: str = "musicxml"
    default_library: str | None = None
    connectivity_available: bool = True
    library_root: str = "osap_library"
    imslp_base_url: str = "https://api.imslp.org"
    resource_auto_install: bool = True
    resource_auto_install_size_threshold: int | None = 1_000_000_000
    github_token: str | None = None
    github_timeout: int = 20
    github_retries: int = 3
    github_cache: bool = True
    openscore_repos: tuple[str, ...] = ("OpenScore/Lieder",)
    imslp_verify_ssl: bool = True
    service_client_id: str | None = None
    service_client_secret: str | None = None
    admin_client_id: str | None = None
    admin_client_secret: str | None = None
    osap_api_db_host: str | None = None
    osap_api_db_user: str | None = None
    osap_api_db_password: str | None = None
    osap_api_db_name: str | None = None
    dev_auth_bypass: bool = False
    storage_web_base: str | None = None
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None
    oidc_spa_origin: str | None = None
    oidc_scope: str = "openid profile"


# Campo -> (variable de entorno, convertidor)
_CONFIG_FIELDS: dict[str, tuple[str, Any]] = {
    "deployment": ("OSAP_DEPLOYMENT", str),
    "dev_mode": ("OSAP_DEV_MODE", int),
    "confidence_threshold": ("OSAP_CONFIDENCE_THRESHOLD", float),
    "max_processing_time": ("OSAP_MAX_PROCESSING_TIME", float),
    "default_quality_level": ("OSAP_DEFAULT_QUALITY_LEVEL", str),
    "default_output_format": ("OSAP_DEFAULT_OUTPUT_FORMAT", str),
    "default_library": ("OSAP_DEFAULT_LIBRARY", str),
    "connectivity_available": ("OSAP_CONNECTIVITY_AVAILABLE", bool),
    "library_root": ("OSAP_LIBRARY_ROOT", str),
    "imslp_base_url": ("OSAP_IMSLP_BASE_URL", str),
    "resource_auto_install": ("OSAP_RESOURCE_AUTO_INSTALL", bool),
    "github_token": ("OSAP_GITHUB_TOKEN", str),
    "github_timeout": ("OSAP_GITHUB_TIMEOUT", int),
    "github_retries": ("OSAP_GITHUB_RETRIES", int),
    "github_cache": ("OSAP_GITHUB_CACHE", bool),
    "imslp_verify_ssl": ("OSAP_IMSLP_VERIFY_SSL", bool),
    "service_client_id": ("OSAP_SERVICE_CLIENT_ID", str),
    "service_client_secret": ("OSAP_SERVICE_CLIENT_SECRET", str),
    "admin_client_id": ("OSAP_ADMIN_CLIENT_ID", str),
    "admin_client_secret": ("OSAP_ADMIN_CLIENT_SECRET", str),
    "oidc_issuer": ("OSAP_OIDC_ISSUER", str),
    "oidc_client_id": ("OSAP_OIDC_CLIENT_ID", str),
    "oidc_client_secret": ("OSAP_OIDC_CLIENT_SECRET", str),
    "oidc_redirect_uri": ("OSAP_OIDC_REDIRECT_URI", str),
    "oidc_spa_origin": ("OSAP_OIDC_SPA_ORIGIN", str),
    "oidc_scope": ("OSAP_OIDC_SCOPE", str),
    "dev_auth_bypass": ("OSAP_DEV_AUTH_BYPASS", bool),
    "storage_web_base": ("OSAP_STORAGE_WEB_BASE", str),
}

# Campo -> (sección TOML, clave) para leer config desde osap.toml (precedencia media).
_TOML_SECTIONS: dict[str, tuple[str, str]] = {
    "deployment": ("osap", "deployment"),
    "dev_mode": ("osap", "dev_mode"),
    "library_root": ("osap", "library_root"),
    "imslp_base_url": ("osap", "imslp_base_url"),
    "default_output_format": ("osap", "default_output_format"),
    "default_quality_level": ("osap", "default_quality_level"),
    "service_client_id": ("service", "client_id"),
    "service_client_secret": ("service", "client_secret"),
    "admin_client_id": ("service", "admin_client_id"),
    "admin_client_secret": ("service", "admin_client_secret"),
    "oidc_issuer": ("oidc", "issuer"),
    "oidc_client_id": ("oidc", "client_id"),
    "oidc_client_secret": ("oidc", "client_secret"),
    "oidc_redirect_uri": ("oidc", "redirect_uri"),
    "oidc_spa_origin": ("oidc", "spa_origin"),
    "oidc_scope": ("oidc", "scope"),
    "dev_auth_bypass": ("osap", "dev_auth_bypass"),
    "storage_web_base": ("osap", "storage_web_base"),
}

# Reglas de validación por servicio.
# Cada entrada es: sección TOML -> lista de campos obligatorios.
_SERVICE_REQUIRED_SECTIONS: dict[str, dict[str, list[str]]] = {
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

# Valores por defecto inseguros detectados en producción.
# Se mantienen como referencia para la validación, pero no se usan como defaults de la dataclass.
_INSECURE_DB_DEFAULTS = {
    "host": "127.0.0.1",
    "user": "osap2027",
    "password": "2027osapdb",
    "name": "osap-api",
}


# -- helpers -------------------------------------------------------------


def _coerce(field: str, raw: Any) -> Any:
    _, conv = _CONFIG_FIELDS.get(field, ("", str))
    if conv is bool:
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if conv is int:
        try:
            return int(str(raw))
        except ValueError:
            return 0
    if conv is float:
        try:
            return float(str(raw))
        except ValueError:
            return 0.0
    return str(raw)


def _load_db_overrides(cfg: Configuration) -> dict[str, Any]:
    """Lee los overrides de config persistidos en la BD operativa (app_config)."""
    try:
        from src.osap.infrastructure.state.op_store import build_op_store

        store = build_op_store(
            host=cfg.osap_api_db_host,
            user=cfg.osap_api_db_user,
            password=cfg.osap_api_db_password,
            database=cfg.osap_api_db_name,
        )
        out: dict[str, Any] = {}
        for field in _CONFIG_FIELDS:
            value = store.get_config(field)
            if value is not None:
                out[field] = _coerce(field, value)
        return out
    except Exception:  # noqa: BLE001
        return {}


def load_configuration(path: str | Path | None = None, service_name: str | None = None) -> Configuration:
    """Carga la configuración: .env > osap.toml (secciones) > BD > entorno > defaults.

    Precedencia final: variable de entorno > .env > osap.toml > BD (app_config) > defaults.
    Carga `.env` del directorio de trabajo (dev) y, si `OSAP_DOTENV` apunta a un fichero
    (p. ej. `.env.production`), también lo carga.

    Si se proporciona `service_name`, valida la configuración contra las reglas del servicio
    antes de devolverla.
    """
    from dotenv import load_dotenv

    load_dotenv()
    dotenv_extra = os.environ.get("OSAP_DOTENV")
    if dotenv_extra:
        load_dotenv(dotenv_extra)

    config_path = Path(path) if path else Path(os.environ.get("OSAP_CONFIG", "osap.toml"))
    data: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    db = data.get("db", {}) if isinstance(data.get("db", None), dict) else {}

    def conn(env: str, key: str) -> str | None:
        return os.environ.get(env) or db.get(key)

    base = Configuration(
        osap_api_db_host=conn("OSAP_API_DB_HOST", "host"),
        osap_api_db_user=conn("OSAP_API_DB_USER", "user"),
        osap_api_db_password=conn("OSAP_API_DB_PASSWORD", "password"),
        osap_api_db_name=conn("OSAP_API_DB_NAME", "name"),
    )

    overrides: dict[str, Any] = _load_db_overrides(base)

    # osap.toml (secciones) — precedencia media (env > osap.toml > BD > defaults).
    for field, (section, key) in _TOML_SECTIONS.items():
        block = data.get(section)
        if isinstance(block, dict) and block.get(key) is not None:
            overrides[field] = _coerce(field, block.get(key))

    for field, (env, _conv) in _CONFIG_FIELDS.items():
        value = os.environ.get(env)
        if value is not None:
            overrides[field] = _coerce(field, value)

    config = Configuration(**{**base.__dict__, **overrides})

    if service_name:
        validate_configuration(config, service_name, data, config_path)

    return config


def validate_configuration(
    config: Configuration,
    service_name: str,
    toml_data: dict[str, Any],
    config_path: Path | None = None,
) -> None:
    """Valida la configuración según el entorno (production/development)."""
    env = os.environ.get("OSAP_ENV", "development").strip().lower()
    if env not in ("production", "development"):
        env = "development"

    rules = _SERVICE_REQUIRED_SECTIONS.get(service_name, {})
    if not rules:
        warnings.warn(
            f"[{service_name}] No hay reglas de validación definidas para este servicio.",
            ConfigurationWarning,
            stacklevel=2,
        )
        return

    if env == "production":
        _validate_strict(service_name, rules, toml_data, config, config_path)
    else:
        _validate_lenient(service_name, rules, toml_data, config, config_path)


def _validate_strict(
    service_name: str,
    rules: dict[str, list[str]],
    toml_data: dict[str, Any],
    config: Configuration,
    config_path: Path | None,
) -> None:
    errors: list[str] = []
    config_ref = str(config_path) if config_path else "osap.toml"

    for section, fields in rules.items():
        if section not in toml_data or not isinstance(toml_data.get(section), dict):
            errors.append(f"Sección obligatoria '{section}' faltante en {config_ref}")
            continue

        section_data = toml_data[section]
        for field in fields:
            raw_value = section_data.get(field)
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                errors.append(f"Campo obligatorio '{section}.{field}' vacío o faltante en {config_ref}")

    # Validar que los campos de BD estén definidos en producción
    db_fields = {
        "host": "OSAP_API_DB_HOST",
        "user": "OSAP_API_DB_USER",
        "password": "OSAP_API_DB_PASSWORD",
        "name": "OSAP_API_DB_NAME",
    }
    for key, env_var in db_fields.items():
        actual = getattr(config, "osap_api_db_" + key, None)
        if not actual:
            errors.append(
                f"Campo 'db.{key}' no definido. Defina {env_var} o actualice {config_ref}."
            )

    if config.dev_auth_bypass:
        errors.append(
            "dev_auth_bypass=true en producción es inseguro. "
            "Desactívelo en osap.toml o mediante OSAP_DEV_AUTH_BYPASS=false."
        )

    if errors:
        raise ConfigurationError(
            service=service_name,
            message="Configuración inválida para producción:\n" + "\n".join(f"  - {e}" for e in errors),
        )


def _validate_lenient(
    service_name: str,
    rules: dict[str, list[str]],
    toml_data: dict[str, Any],
    config: Configuration,
    config_path: Path | None,
) -> None:
    warnings_list: list[str] = []
    config_ref = str(config_path) if config_path else "osap.toml"

    for section, fields in rules.items():
        if section not in toml_data or not isinstance(toml_data.get(section), dict):
            warnings_list.append(f"Sección recomendada '{section}' faltante en {config_ref}")
            continue

        section_data = toml_data[section]
        for field in fields:
            raw_value = section_data.get(field)
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                warnings_list.append(f"Campo '{section}.{field}' vacío o faltante en {config_ref}")

    db_fields = {
        "host": "OSAP_API_DB_HOST",
        "user": "OSAP_API_DB_USER",
        "password": "OSAP_API_DB_PASSWORD",
        "name": "OSAP_API_DB_NAME",
    }
    for key, env_var in db_fields.items():
        actual = getattr(config, "osap_api_db_" + key, None)
        if not actual:
            warnings_list.append(f"Campo 'db.{key}' no definido (defina {env_var} o actualice {config_ref})")

    for warning_msg in warnings_list:
        warnings.warn(
            f"[{service_name}] Configuración (dev): {warning_msg}",
            ConfigurationWarning,
            stacklevel=2,
        )
