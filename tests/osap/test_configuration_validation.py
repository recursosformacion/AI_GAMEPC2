"""Tests de validación de configuración (OSAP_ENV).

Verifican el comportamiento estricto en producción y permisivo en desarrollo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.osap.bootstrap.configuration import (
    Configuration,
    ConfigurationError,
    ConfigurationWarning,
    _validate_lenient,
    _validate_strict,
    validate_configuration,
)

_MINIMAL_TOML = """
[db]
host = "127.0.0.1"
name = "osap-api"
user = "osap2027"
password = "2027osapdb"

[oidc]
issuer = "http://osap-auth/auth-api"
client_id = "osap-api"
redirect_uri = "http://osap-app/api/v1/auth/oidc/callback"
client_secret = "dev-secret"
"""


def _toml(data: str) -> dict[str, object]:
    import tomllib

    return tomllib.loads(data)


def _config(**overrides: object) -> Configuration:
    defaults: dict[str, object] = {
        "osap_api_db_host": None,
        "osap_api_db_user": None,
        "osap_api_db_password": None,
        "osap_api_db_name": None,
        "dev_auth_bypass": False,
    }
    defaults.update(overrides)
    return Configuration(**defaults)


class TestValidateStrict:
    def test_ok_when_all_required_sections_present(self) -> None:
        data = _toml(_MINIMAL_TOML)
        config = _config(
            osap_api_db_host="db.prod",
            osap_api_db_user="admin",
            osap_api_db_password="secret",
            osap_api_db_name="prod_db",
        )
        _validate_strict("osap-api", {"db": ["host", "name", "user", "password"], "oidc": ["issuer", "client_id", "redirect_uri", "client_secret"]}, data, config, Path("osap.toml"))  # noqa: E501

    def test_raises_when_section_missing(self) -> None:
        data = _toml("[db]\nhost = '127.0.0.1'\n")
        config = _config(
            osap_api_db_host="127.0.0.1",
            osap_api_db_user="osap2027",
            osap_api_db_password="2027osapdb",
            osap_api_db_name="osap-api",
        )
        with pytest.raises(ConfigurationError, match="Sección obligatoria 'oidc'"):
            _validate_strict("osap-api", {"db": ["host"], "oidc": ["issuer"]}, data, config, Path("osap.toml"))

    def test_raises_when_field_empty(self) -> None:
        data = _toml("[db]\nhost = '127.0.0.1'\nname = ''\n[oidc]\nissuer = 'http://x'\nclient_id = 'id'\nredirect_uri = 'http://x'\nclient_secret = ''\n")  # noqa: E501
        config = _config(
            osap_api_db_host="127.0.0.1",
            osap_api_db_user="osap2027",
            osap_api_db_password="2027osapdb",
            osap_api_db_name="osap-api",
        )
        with pytest.raises(ConfigurationError, match="Campo obligatorio 'db.name'"):
            _validate_strict("osap-api", {"db": ["host", "name"], "oidc": ["client_secret"]}, data, config, Path("osap.toml"))  # noqa: E501

    def test_raises_when_db_fields_missing(self) -> None:
        config = _config()
        data = _toml(_MINIMAL_TOML)
        with pytest.raises(ConfigurationError, match="Campo 'db.host' no definido"):
            _validate_strict("osap-api", {"db": ["host"], "oidc": ["issuer"]}, data, config, Path("osap.toml"))

    def test_ok_when_db_fields_provided(self) -> None:
        config = _config(
            osap_api_db_host="db.prod",
            osap_api_db_user="admin",
            osap_api_db_password="secret",
            osap_api_db_name="prod_db",
        )
        data = _toml(_MINIMAL_TOML)
        _validate_strict("osap-api", {"db": ["host"], "oidc": ["issuer"]}, data, config, Path("osap.toml"))

    def test_raises_when_dev_auth_bypass_enabled(self) -> None:
        config = _config(
            osap_api_db_host="db.prod",
            osap_api_db_user="admin",
            osap_api_db_password="secret",
            osap_api_db_name="prod_db",
            dev_auth_bypass=True,
        )
        data = _toml(_MINIMAL_TOML)
        with pytest.raises(ConfigurationError, match="dev_auth_bypass"):
            _validate_strict("osap-api", {"db": ["host"], "oidc": ["issuer"]}, data, config, Path("osap.toml"))


class TestValidateLenient:
    def test_warns_when_section_missing(self) -> None:
        data = _toml("[db]\nhost = '127.0.0.1'\n")
        config = _config(
            osap_api_db_host="127.0.0.1",
            osap_api_db_user="osap2027",
            osap_api_db_password="2027osapdb",
            osap_api_db_name="osap-api",
        )
        with pytest.warns(ConfigurationWarning, match="Sección recomendada 'oidc'"):
            _validate_lenient("osap-api", {"db": ["host"], "oidc": ["issuer"]}, data, config, Path("osap.toml"))

    def test_does_not_raise_on_empty_field(self) -> None:
        data = _toml("[db]\nhost = '127.0.0.1'\nname = ''\n")
        config = _config(
            osap_api_db_host="127.0.0.1",
            osap_api_db_user="osap2027",
            osap_api_db_password="2027osapdb",
            osap_api_db_name="osap-api",
        )
        with pytest.warns(ConfigurationWarning, match="Campo 'db.name'"):
            _validate_lenient("osap-api", {"db": ["host", "name"]}, data, config, Path("osap.toml"))

    def test_warns_when_db_missing(self) -> None:
        config = _config()
        data = _toml("[oidc]\nissuer = 'http://x'\n")
        with pytest.warns(ConfigurationWarning, match="Campo 'db.host' no definido"):
            _validate_lenient("osap-api", {"db": ["host"], "oidc": ["issuer"]}, data, config, Path("osap.toml"))


class TestValidateConfigurationIntegration:
    def test_production_mode_requires_sections(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OSAP_ENV", "production")
        data = _toml("[db]\nhost = 'db.prod'\nname = 'prod_db'\nuser = 'admin'\npassword = 'secret'\n[oidc]\nissuer = 'http://x'\nclient_id = 'id'\nredirect_uri = 'http://x'\nclient_secret = 'secret'\n")  # noqa: E501
        config = _config(
            osap_api_db_host="db.prod",
            osap_api_db_user="admin",
            osap_api_db_password="secret",
            osap_api_db_name="prod_db",
        )
        validate_configuration(config, "osap-api", data, Path("osap.toml"))

    def test_development_mode_warns_but_continues(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OSAP_ENV", "development")
        data = _toml("[db]\nhost = '127.0.0.1'\n")
        config = _config()
        with pytest.warns(ConfigurationWarning, match="Sección recomendada 'oidc'"):
            validate_configuration(config, "osap-api", data, Path("osap.toml"))

    def test_unknown_service_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OSAP_ENV", "production")
        config = _config(
            osap_api_db_host="db.prod",
            osap_api_db_user="admin",
            osap_api_db_password="secret",
            osap_api_db_name="prod_db",
        )
        with pytest.warns(ConfigurationWarning, match="No hay reglas de validación"):
            validate_configuration(config, "unknown-service", {}, Path("osap.toml"))
