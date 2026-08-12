import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Configuration:
    """Configuración de osap-api.

    Los valores viven centralizados en la BD operativa (`app_config`), con defaults en
    código y override por variable de entorno. El fichero osap.toml SOLO contiene la
    conexión a la BD ([db]). `deployment` (prod/dev) y `dev_mode` deciden las rutas.
    """

    deployment: str = "prod"  # "prod" (real, escribible) | "dev" (dev_mode decide rutas)
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
    osap_api_db_host: str = "127.0.0.1"
    osap_api_db_user: str = "osap2027"
    osap_api_db_password: str = "2027osapdb"
    osap_api_db_name: str = "osap-api"


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
}


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


def load_configuration(path: str | Path | None = None) -> Configuration:
    """Carga la configuración: osap.toml (solo [db]) > BD operativa > entorno > defaults.

    Precedencia final: variable de entorno > BD (app_config) > osap.toml ([db]) > defaults.
    """
    config_path = Path(path) if path else Path(os.environ.get("OSAP_CONFIG", "osap.toml"))
    data: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    db = data.get("db", {}) if isinstance(data.get("db", None), dict) else {}

    def conn(env: str, key: str, default: str) -> str:
        return os.environ.get(env, str(db.get(key, default)))

    base = Configuration(
        osap_api_db_host=conn("OSAP_API_DB_HOST", "host", "127.0.0.1"),
        osap_api_db_user=conn("OSAP_API_DB_USER", "user", "osap2027"),
        osap_api_db_password=conn("OSAP_API_DB_PASSWORD", "password", "2027osapdb"),
        osap_api_db_name=conn("OSAP_API_DB_NAME", "name", "osap-api"),
    )

    overrides: dict[str, Any] = _load_db_overrides(base)

    for field, (env, _conv) in _CONFIG_FIELDS.items():
        value = os.environ.get(env)
        if value is not None:
            overrides[field] = _coerce(field, value)

    return Configuration(**{**base.__dict__, **overrides})
