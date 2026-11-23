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
    _load_db_overrides,
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
jwks_url = "http://osap-auth/auth/.well-known/jwks.json"
audience = "osap-api"
token_issuer = "http://osap-auth"

[service]
client_id = "osap-api"
client_secret = "service-secret"
admin_client_id = "osap-composer-admin-service"
admin_client_secret = "admin-secret"
support_admin_client_id = "support-admin-service"
support_admin_client_secret = "support-admin-secret"

[news]
base_url = "http://127.0.0.1:8401"
service_token = "news-token"

[ads]
base_url = "http://127.0.0.1:8305"
service_token = "ads-token"
web_base = "http://127.0.0.1:8305"
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
        with pytest.raises(ConfigurationError, match="Campo obligatorio 'oidc.issuer'"):
            _validate_strict("osap-api", {"db": ["host"], "oidc": ["issuer"]}, data, config, Path("osap.toml"))

    def test_raises_when_field_empty(self) -> None:
        data = _toml("[db]\nhost = '127.0.0.1'\nname = ''\n[oidc]\nissuer = 'http://x'\nclient_id = 'id'\nredirect_uri = 'http://x'\nclient_secret = ''\n")  # noqa: E501
        config = _config(
            osap_api_db_host="127.0.0.1",
            osap_api_db_user="osap2027",
            osap_api_db_password="2027osapdb",
            osap_api_db_name="",
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
        with pytest.warns(ConfigurationWarning, match="Campo 'oidc.issuer'"):
            _validate_lenient("osap-api", {"db": ["host"], "oidc": ["issuer"]}, data, config, Path("osap.toml"))

    def test_does_not_raise_on_empty_field(self) -> None:
        data = _toml("[db]\nhost = '127.0.0.1'\nname = ''\n")
        config = _config(
            osap_api_db_host="127.0.0.1",
            osap_api_db_user="osap2027",
            osap_api_db_password="2027osapdb",
            osap_api_db_name="",
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
        data = _toml(
            "[db]\nhost = 'db.prod'\nname = 'prod_db'\nuser = 'admin'\npassword = 'secret'\n"
            "[oidc]\nissuer = 'http://x'\nclient_id = 'id'\nredirect_uri = 'http://x'\n"
            "client_secret = 'secret'\njwks_url = 'http://x/jwks'\naudience = 'osap-api'\n"
            "token_issuer = 'http://x'\n"
            "[service]\nclient_id = '11111111-1111-4111-8111-111111111111'\nclient_secret = 'secret'\n"
            "admin_client_id = '22222222-2222-4222-8222-222222222222'\nadmin_client_secret = 'secret'\n"
            "support_admin_client_id = '33333333-3333-4333-8333-333333333333'\n"
            "support_admin_client_secret = 'support-secret'\n"
            "[news]\nbase_url = 'http://127.0.0.1:8401'\nservice_token = 'news'\n"
            "[ads]\nbase_url = 'http://127.0.0.1:8305'\nservice_token = 'ads'\n"
            "web_base = 'http://127.0.0.1:8305'\n"
        )
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
        config = _config(deployment="development")
        with pytest.warns(ConfigurationWarning, match="Campo 'oidc.issuer'"):
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



def test_db_overrides_are_skipped_without_explicit_connection() -> None:
    """No debe intentarse una conexión con credenciales fallback incrustadas."""
    assert _load_db_overrides(_config()) == {}



def test_production_validation_accepts_centralized_effective_configuration() -> None:
    """Las credenciales pueden venir de app_config/env; no se duplican en TOML."""
    config = _config(
        osap_api_db_host="db.prod",
        osap_api_db_user="db-user",
        osap_api_db_password="db-secret",
        osap_api_db_name="osap_api",
        oidc_issuer="https://auth.example",
        oidc_client_id="osap-api",
        oidc_redirect_uri="https://api.example/callback",
        oidc_client_secret="oidc-secret",
        oidc_jwks_url="https://auth.example/jwks",
        oidc_audience="osap-api",
        oidc_token_issuer="https://auth.example",
        service_client_id="11111111-1111-4111-8111-111111111111",
        service_client_secret="service-secret",
        admin_client_id="22222222-2222-4222-8222-222222222222",
        admin_client_secret="admin-secret",
        support_admin_client_id="33333333-3333-4333-8333-333333333333",
        support_admin_client_secret="support-admin-secret",
        news_api_base="http://127.0.0.1:8401",
        news_api_token="news-token",
        ads_base_url="http://127.0.0.1:8305",
        ads_service_token="ads-token",
        ads_web_base="http://127.0.0.1:8305",
    )
    _validate_strict(
        "osap-api",
        {
            "db": ["host", "name", "user", "password"],
            "oidc": ["issuer", "client_id", "redirect_uri", "client_secret", "jwks_url", "audience", "token_issuer"],
            "service": [
                "client_id",
                "client_secret",
                "admin_client_id",
                "admin_client_secret",
                "support_admin_client_id",
                "support_admin_client_secret",
            ],
            "news": ["base_url", "service_token"],
            "ads": ["base_url", "service_token", "web_base"],
        },
        {},
        config,
        Path("osap.toml"),
    )



def test_prod_deployment_uses_strict_validation_without_osap_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OSAP_ENV", raising=False)
    config = _config(deployment="prod")
    with pytest.raises(ConfigurationError):
        validate_configuration(config, "osap-api", {}, Path("osap.toml"))
