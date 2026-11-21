"""Contratos de handoff POST para los paneles de administración externos."""

from __future__ import annotations

from src.osap.api.platform.system import SystemMixin


class _SupportClient:
    base_url = "http://127.0.0.1:8300"

    def admin_token(self) -> str:
        return "SUPPORT-TOKEN"


class _Container:
    def dev_auth_bypass(self) -> bool:
        return False

    def storage_web_base(self) -> str:
        return "https://storage.example"

    def support_admin_recognitions(self) -> _SupportClient:
        return _SupportClient()

    def support_web_base(self) -> str:
        return "https://support.example/support-api"

    def ads_web_base(self) -> str:
        return "https://ads.example/publicidad"

    def ads_base_url(self) -> str:
        return "https://ads.example/publicidad"


class _Api(SystemMixin):
    def __init__(self) -> None:
        self._container = _Container()

    def _require_admin(self, token: str | None) -> None:
        return None


def test_support_handoff_uses_relative_redirect_for_proxy_prefix() -> None:
    result = _Api().support_web("admin-token", "recognitions")
    assert result == {
        "url": "https://support.example/support-api/api/v1/admin/web/session",
        "token": "SUPPORT-TOKEN",
        "next": "./recognitions",
    }


def test_ads_handoff_keeps_same_origin_public_path() -> None:
    result = _Api().ads_web("user-access-token")
    assert result == {
        "url": "https://ads.example/publicidad/auth/session",
        "token": "user-access-token",
        "next": "https://ads.example/publicidad/p",
    }
    assert "?token=" not in result["url"]
