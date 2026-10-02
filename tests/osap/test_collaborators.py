"""Fachada pública de colaboradores: composición y clientes support/auth."""

from __future__ import annotations

import pytest
import requests

from src.osap.application.collaborators import (
    CollaboratorsUnavailableError,
    ComposePublicCollaboratorsUseCase,
    PublicProjectNotFoundError,
)
from src.osap.infrastructure.auth import public_names_client as pnc
from src.osap.infrastructure.auth.public_names_client import PublicNamesClient
from src.osap.infrastructure.auth.service_token_provider import StaticServiceTokenProvider
from src.osap.infrastructure.support import public_recognitions_client as prc
from src.osap.infrastructure.support.public_recognitions_client import (
    SupportPublicRecognitionsClient,
)


class _Rec:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def public_project_recognitions(self, project: str) -> list[dict]:
        return self.rows


class _Names:
    def __init__(self, mapping: dict[str, str | None]) -> None:
        self.mapping = mapping
        self.seen: list[str] = []

    def names(self, user_ids: list[str]) -> dict[str, str | None]:
        self.seen = user_ids
        return self.mapping


class _Resp:
    def __init__(self, status: int, doc: object) -> None:
        self.status_code = status
        self._doc = doc

    def json(self) -> object:
        if self._doc is None:
            raise ValueError("no json")
        return self._doc


def test_compose_omits_missing_or_null_name_and_never_exposes_user_id() -> None:
    rows = [
        {"user_id": "u1", "recognitions": [{"type": "contributor", "granted_at": "2026-01-01"}]},
        {"user_id": "u2", "recognitions": [{"type": "voice", "granted_at": "2026-02-01"}]},
        {"user_id": "u3", "recognitions": [{"type": "supporter", "granted_at": "2026-03-01"}]},
    ]
    names = _Names({"u1": "Ana", "u2": None})  # u2 sin nombre; u3 eliminado (ausente)
    uc = ComposePublicCollaboratorsUseCase(recognitions=_Rec(rows), names=names)

    result = uc.execute("omr")

    assert result == [
        {"name": "Ana", "recognitions": [{"type": "contributor", "granted_at": "2026-01-01"}]}
    ]
    assert names.seen == ["u1", "u2", "u3"]
    assert "user_id" not in result[0]


def test_support_public_parses_and_quotes(monkeypatch) -> None:
    visto: dict[str, str] = {}

    def _get(url: str, **k: object) -> object:
        visto["url"] = url
        return _Resp(200, [{"user_id": "u1", "recognitions": [{"type": "voice", "granted_at": "x"}]}])

    monkeypatch.setattr(prc.requests, "get", _get)
    client = SupportPublicRecognitionsClient(base_url="http://support")
    rows = client.public_project_recognitions("o mr")

    assert rows == [{"user_id": "u1", "recognitions": [{"type": "voice", "granted_at": "x"}]}]
    assert "o%20mr" in visto["url"]


def test_support_public_404_is_project_not_found(monkeypatch) -> None:
    monkeypatch.setattr(prc.requests, "get", lambda *a, **k: _Resp(404, {}))
    client = SupportPublicRecognitionsClient(base_url="http://support")
    with pytest.raises(PublicProjectNotFoundError):
        client.public_project_recognitions("nope")


def test_support_public_http_error_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(prc.requests, "get", lambda *a, **k: _Resp(500, {}))
    client = SupportPublicRecognitionsClient(base_url="http://support")
    with pytest.raises(CollaboratorsUnavailableError):
        client.public_project_recognitions("omr")


def test_names_batches_at_500_and_parses(monkeypatch) -> None:
    urls: list[str] = []

    def _get(url: str, **k: object) -> object:
        urls.append(url)
        ids = url.split("ids=", 1)[1].split(",")
        return _Resp(200, [{"id": i, "name": f"n-{i}"} for i in ids])

    monkeypatch.setattr(pnc.requests, "get", _get)
    client = PublicNamesClient(
        base_url="http://auth",
        token_provider=StaticServiceTokenProvider("tok"),
        batch_size=2,
    )
    result = client.names(["a", "b", "c", "a"])

    assert result == {"a": "n-a", "b": "n-b", "c": "n-c"}
    assert len(urls) == 2  # 3 únicos con lote de 2


def test_names_token_failure_is_unavailable() -> None:
    class _Bad:
        def token(self, scopes: tuple[str, ...]) -> str:
            raise RuntimeError("auth caido")

    client = PublicNamesClient(base_url="http://auth", token_provider=_Bad())
    with pytest.raises(CollaboratorsUnavailableError):
        client.names(["a"])


def test_names_http_error_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(pnc.requests, "get", lambda *a, **k: _Resp(403, {}))
    client = PublicNamesClient(
        base_url="http://auth", token_provider=StaticServiceTokenProvider("tok")
    )
    with pytest.raises(CollaboratorsUnavailableError):
        client.names(["a"])


def test_names_network_error_is_unavailable(monkeypatch) -> None:
    def _get(*a: object, **k: object) -> object:
        raise requests.RequestException("timeout")

    monkeypatch.setattr(pnc.requests, "get", _get)
    client = PublicNamesClient(
        base_url="http://auth", token_provider=StaticServiceTokenProvider("tok")
    )
    with pytest.raises(CollaboratorsUnavailableError):
        client.names(["a"])
