import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Configuration:
    confidence_threshold: float = 0.8
    max_processing_time: float = 300.0
    default_quality_level: str = "full_notation"
    default_output_format: str = "musicxml"
    default_library: str | None = None
    connectivity_available: bool = True
    library_root: str = "osap_library"
    imslp_base_url: str = "https://api.imslp.org"
    resource_auto_install: bool = True
    resource_auto_install_size_threshold: int | None = 1_000_000_000  # 1 GB
    github_token: str | None = None
    github_timeout: int = 20
    github_retries: int = 3
    github_cache: bool = True
    openscore_repos: tuple[str, ...] = ("OpenScore/Lieder",)
    imslp_verify_ssl: bool = True
    omr_base_url: str | None = None
    omr_api_key: str | None = None
    dev_mode: int = 0
    service_client_id: str | None = None
    service_client_secret: str | None = None
    admin_client_id: str | None = None
    admin_client_secret: str | None = None
    osap_auth_token_url: str | None = None
    osap_auth_base_url: str | None = None
    osap_api_db_host: str = "127.0.0.1"
    osap_api_db_user: str = "osap2027"
    osap_api_db_password: str = "2027osapdb"
    osap_api_db_name: str = "osap-api"
    credentials_path: str = "osap_credentials.db"
    credentials_key: str | None = None


# Campo -> (sección TOML, clave TOML, variable de entorno)
_CONFIG_FIELDS: dict[str, tuple[str, str, str]] = {
    "library_root": ("osap", "library_root", "OSAP_LIBRARY_ROOT"),
    "imslp_base_url": ("osap", "imslp_base_url", "OSAP_IMSLP_BASE_URL"),
    "omr_base_url": ("omr", "base_url", "OSAP_OMR_BASE_URL"),
    "omr_api_key": ("omr", "api_key", "OSAP_OMR_API_KEY"),
    "dev_mode": ("osap", "dev_mode", "OSAP_DEV_MODE"),
    "service_client_id": ("service", "client_id", "OSAP_SERVICE_CLIENT_ID"),
    "service_client_secret": ("service", "client_secret", "OSAP_SERVICE_CLIENT_SECRET"),
    "admin_client_id": ("service", "admin_client_id", "OSAP_ADMIN_CLIENT_ID"),
    "admin_client_secret": ("service", "admin_client_secret", "OSAP_ADMIN_CLIENT_SECRET"),
    "osap_auth_token_url": ("auth", "token_url", "OSAP_AUTH_TOKEN_URL"),
    "osap_auth_base_url": ("auth", "base_url", "OSAP_AUTH_BASE_URL"),
    "osap_api_db_host": ("osap", "db_host", "OSAP_API_DB_HOST"),
    "osap_api_db_user": ("osap", "db_user", "OSAP_API_DB_USER"),
    "osap_api_db_password": ("osap", "db_password", "OSAP_API_DB_PASSWORD"),
    "osap_api_db_name": ("osap", "db_name", "OSAP_API_DB_NAME"),
}


def load_configuration(path: str | Path | None = None) -> Configuration:
    """Carga la configuración combinando defaults + fichero TOML + variables de entorno.

    Precedencia: variable de entorno > fichero (osap.toml o el indicado) > defaults.
    """
    config_path = Path(path) if path else Path(os.environ.get("OSAP_CONFIG", "osap.toml"))
    data: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    kwargs: dict[str, Any] = {}
    for field, (section, key, env) in _CONFIG_FIELDS.items():
        value = os.environ.get(env)
        if value is None:
            block = data.get(section)
            if isinstance(block, dict):
                value = block.get(key)
        if value is not None:
            if field == "dev_mode":
                try:
                    parsed: object = int(str(value))
                except ValueError:
                    parsed = 0
                kwargs[field] = parsed
            else:
                kwargs[field] = value
    return Configuration(**kwargs)


def _dump_toml(data: dict[str, Any]) -> str:
    """Serializa un dict (secciones + escalares) a TOML, para configs simples."""
    lines: list[str] = []
    for key, value in data.items():
        if not isinstance(value, dict):
            lines.append(f"{key} = {_toml_repr(value)}")
    for section, block in data.items():
        if not isinstance(block, dict):
            continue
        lines.append(f"\n[{section}]")
        for key, value in block.items():
            lines.append(f"{key} = {_toml_repr(value)}")
    return "\n".join(lines) + "\n"


def _toml_repr(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_repr(item) for item in value) + "]"
    return '""'
