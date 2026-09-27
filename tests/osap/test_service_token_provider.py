"""Provider de service token: incluye `audience` explícita (fase 4.2 support M2M)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.osap.infrastructure.auth import service_token_provider as stp

if TYPE_CHECKING:
    import urllib.request


class _Resp:
    def __init__(self, doc: dict[str, object]) -> None:
        self._doc = doc

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self._doc).encode()


def _capture(monkeypatch) -> dict[str, object]:
    seen: dict[str, object] = {}

    def _urlopen(request: urllib.request.Request, timeout: int | None = None) -> _Resp:
        assert request.data is not None
        seen["body"] = json.loads(request.data.decode())
        return _Resp({"access_token": "tok"})

    monkeypatch.setattr(stp.urllib.request, "urlopen", _urlopen)
    return seen


def test_incluye_audience_cuando_se_especifica(monkeypatch) -> None:
    seen = _capture(monkeypatch)
    provider = stp.ClientCredentialsServiceTokenProvider(
        "cid", "sec", "http://auth/oauth/token", audience="osap-support"
    )
    assert provider.token(("api:read",)) == "tok"
    assert seen["body"]["audience"] == "osap-support"
    assert seen["body"]["scope"] == "api:read"


def test_sin_audience_no_envia_la_clave(monkeypatch) -> None:
    seen = _capture(monkeypatch)
    provider = stp.ClientCredentialsServiceTokenProvider("cid", "sec", "http://auth/oauth/token")
    provider.token(("storage:read",))
    assert "audience" not in seen["body"]
