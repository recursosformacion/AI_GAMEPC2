"""Mapeo de secciones de la web de administración de osap-storage (`storage_web`)."""

from __future__ import annotations

from src.osap.api.platform.system import SystemMixin


class _Container:
    def storage_web_base(self) -> str:
        return "https://storage.example"

    def dev_auth_bypass(self) -> bool:
        return False


class _Composers:
    def storage_admin_token(self) -> str:
        return "TOK"


class _Api(SystemMixin):
    def __init__(self) -> None:
        self._container = _Container()

    def _require_admin(self, token: str | None) -> None:
        return None

    def composers(self) -> _Composers:
        return _Composers()


def _url(section: str | None) -> str:
    return _Api().storage_web("admin-token", section)


def test_secciones_curadas() -> None:
    assert _url("composers") == "https://storage.example/admin/maestros?token=TOK"
    assert _url("works") == "https://storage.example/admin/obras?token=TOK"
    assert _url("representations") == "https://storage.example/admin/representations?token=TOK"
    assert _url("mantenimiento") == "https://storage.example/admin/mantenimiento?token=TOK"
    assert _url("multimantenimiento") == "https://storage.example/admin/?token=TOK"
    assert _url("tables") == "https://storage.example/admin?token=TOK&tab=tables"
    assert _url(None) == "https://storage.example/admin?token=TOK"


def test_deep_link_por_tabla() -> None:
    assert _url("table:instruments") == "https://storage.example/admin/t/instruments?token=TOK"
    assert _url("table:genre_mappings") == "https://storage.example/admin/t/genre_mappings?token=TOK"


def test_tabla_invalida_cae_al_generico() -> None:
    # Nombres fuera del patrón permitido no se interpolan (anti-inyección).
    assert _url("table:../etc/passwd") == "https://storage.example/admin?token=TOK"
    assert _url("table:Instruments") == "https://storage.example/admin?token=TOK"
