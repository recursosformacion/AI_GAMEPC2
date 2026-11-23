"""Mapeo de destinos y datos de handoff POST para osap-storage."""

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


def _handoff(section: str | None) -> dict[str, str]:
    return _Api().storage_web("admin-token", section)


def test_secciones_curadas() -> None:
    assert _handoff("composers") == {
        "url": "https://storage.example/admin/session",
        "token": "TOK",
        "next": "/admin/maestros",
    }
    assert _handoff("works")["next"] == "/admin/obras"
    assert _handoff("representations")["next"] == "/admin/representations"
    assert _handoff("work-persons")["next"] == "/admin/work-persons"
    assert _handoff("mantenimiento")["next"] == "/admin/mantenimiento"
    assert _handoff("multimantenimiento")["next"] == "/admin/"
    assert _handoff("tables")["next"] == "/admin?tab=tables"
    assert _handoff(None)["next"] == "/admin"
    assert all("?token=" not in value for value in _handoff(None).values())


def test_deep_link_por_tabla() -> None:
    assert _handoff("table:instruments")["next"] == "/admin/t/instruments"
    assert _handoff("table:genre_mappings")["next"] == "/admin/t/genre_mappings"


def test_tabla_invalida_cae_al_generico() -> None:
    assert _handoff("table:../etc/passwd")["next"] == "/admin"
    assert _handoff("table:Instruments")["next"] == "/admin"
