"""Fachada pública de colaboradores: composición y clientes M2M support/auth."""

from __future__ import annotations

import pytest
import requests

from src.osap.application.collaborators import (
    CollaboratorsUnavailableError,
    ComposePublicCollaboratorsUseCase,
    PublicProfile,
    PublicProjectNotFoundError,
    PublicUser,
)
from src.osap.infrastructure.auth import public_profiles_client as ppc
from src.osap.infrastructure.auth.public_profiles_client import PublicProfilesClient
from src.osap.infrastructure.auth.service_token_provider import StaticServiceTokenProvider
from src.osap.infrastructure.support import recognitions_client as recs
from src.osap.infrastructure.support.recognitions_client import SupportRecognitionsClient


class _Rec:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def active_project_recognitions(self, project: str) -> list[dict]:
        return self.rows


class _Profiles:
    def __init__(self, users: list[PublicUser]) -> None:
        self.users = users

    def public_users(self) -> list[PublicUser]:
        return self.users


class _Resp:
    def __init__(self, status: int, doc: object) -> None:
        self.status_code = status
        self._doc = doc

    def json(self) -> object:
        if self._doc is None:
            raise ValueError("no json")
        return self._doc


def test_compose_lists_all_public_users_and_attaches_badges() -> None:
    # La lista la dirige auth (usuarios públicos con nickname). Support solo aporta badges.
    users = [PublicUser("u1", "ana"), PublicUser("u2", "bob")]
    rows = [
        {"user_id": "u1", "recognitions": [{"type": "contributor", "granted_at": "2026-01-01"}]},
        # u2 público sin reconocimientos → aparece con badges vacíos
    ]
    uc = ComposePublicCollaboratorsUseCase(recognitions=_Rec(rows), profiles=_Profiles(users))

    result = uc.execute("omr")

    assert result == [
        {"nickname": "ana", "recognitions": [{"type": "contributor", "granted_at": "2026-01-01"}]},
        {"nickname": "bob", "recognitions": []},
    ]
    assert "user_id" not in result[0]
    assert "name" not in result[0]


def test_support_recognitions_parses_quotes_and_uses_token(monkeypatch) -> None:
    visto: dict[str, str] = {}

    def _get(url: str, **k: object) -> object:
        visto["url"] = url
        visto["auth"] = str(k.get("headers"))
        return _Resp(
            200, [{"user_id": "u1", "recognitions": [{"type": "voice", "granted_at": "x"}]}]
        )

    monkeypatch.setattr(recs.requests, "get", _get)
    client = SupportRecognitionsClient(
        base_url="http://support", token_provider=StaticServiceTokenProvider("tok")
    )
    rows = client.active_project_recognitions("o mr")

    assert rows == [{"user_id": "u1", "recognitions": [{"type": "voice", "granted_at": "x"}]}]
    assert "o%20mr" in visto["url"]
    assert "/api/v1/m2m/recognitions?project=" in visto["url"]
    assert "Bearer tok" in visto["auth"]


def test_support_recognitions_404_is_project_not_found(monkeypatch) -> None:
    monkeypatch.setattr(recs.requests, "get", lambda *a, **k: _Resp(404, {}))
    client = SupportRecognitionsClient(
        base_url="http://support", token_provider=StaticServiceTokenProvider("tok")
    )
    with pytest.raises(PublicProjectNotFoundError):
        client.active_project_recognitions("nope")


def test_support_recognitions_http_error_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(recs.requests, "get", lambda *a, **k: _Resp(500, {}))
    client = SupportRecognitionsClient(
        base_url="http://support", token_provider=StaticServiceTokenProvider("tok")
    )
    with pytest.raises(CollaboratorsUnavailableError):
        client.active_project_recognitions("omr")


def test_support_recognitions_token_failure_is_unavailable() -> None:
    class _Bad:
        def token(self, scopes: tuple[str, ...]) -> str:
            raise RuntimeError("auth caido")

    client = SupportRecognitionsClient(base_url="http://support", token_provider=_Bad())
    with pytest.raises(CollaboratorsUnavailableError):
        client.active_project_recognitions("omr")


def test_support_recognitions_network_error_is_unavailable(monkeypatch) -> None:
    def _get(*a: object, **k: object) -> object:
        raise requests.RequestException("timeout")

    monkeypatch.setattr(recs.requests, "get", _get)
    client = SupportRecognitionsClient(
        base_url="http://support", token_provider=StaticServiceTokenProvider("tok")
    )
    with pytest.raises(CollaboratorsUnavailableError):
        client.active_project_recognitions("omr")


def test_profiles_batches_at_500_and_parses_consent(monkeypatch) -> None:
    urls: list[str] = []

    def _get(url: str, **k: object) -> object:
        urls.append(url)
        ids = url.split("ids=", 1)[1].split(",")
        return _Resp(
            200,
            [
                {"id": i, "name": f"n-{i}", "nickname": f"nick-{i}", "nickname_public_consent": True}
                for i in ids
            ],
        )

    monkeypatch.setattr(ppc.requests, "get", _get)
    client = PublicProfilesClient(
        base_url="http://auth",
        token_provider=StaticServiceTokenProvider("tok"),
        batch_size=2,
    )
    result = client.public_profiles(["a", "b", "c", "a"])

    assert result == {
        "a": PublicProfile(nickname="nick-a", nickname_public_consent=True),
        "b": PublicProfile(nickname="nick-b", nickname_public_consent=True),
        "c": PublicProfile(nickname="nick-c", nickname_public_consent=True),
    }
    assert len(urls) == 2  # 3 únicos con lote de 2


def test_public_users_parses_list(monkeypatch) -> None:
    def _get(url: str, **k: object) -> object:
        assert url.endswith("/auth/m2m/public-users")
        return _Resp(
            200,
            [{"id": "u1", "nickname": "ana"}, {"id": "u2", "nickname": None}, "basura"],
        )

    monkeypatch.setattr(ppc.requests, "get", _get)
    client = PublicProfilesClient(
        base_url="http://auth", token_provider=StaticServiceTokenProvider("tok")
    )
    assert client.public_users() == [PublicUser(user_id="u1", nickname="ana")]


def test_profiles_token_failure_is_unavailable() -> None:
    class _Bad:
        def token(self, scopes: tuple[str, ...]) -> str:
            raise RuntimeError("auth caido")

    client = PublicProfilesClient(base_url="http://auth", token_provider=_Bad())
    with pytest.raises(CollaboratorsUnavailableError):
        client.public_profiles(["a"])


def test_profiles_http_error_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(ppc.requests, "get", lambda *a, **k: _Resp(403, {}))
    client = PublicProfilesClient(
        base_url="http://auth", token_provider=StaticServiceTokenProvider("tok")
    )
    with pytest.raises(CollaboratorsUnavailableError):
        client.public_profiles(["a"])


def test_profiles_network_error_is_unavailable(monkeypatch) -> None:
    def _get(*a: object, **k: object) -> object:
        raise requests.RequestException("timeout")

    monkeypatch.setattr(ppc.requests, "get", _get)
    client = PublicProfilesClient(
        base_url="http://auth", token_provider=StaticServiceTokenProvider("tok")
    )
    with pytest.raises(CollaboratorsUnavailableError):
        client.public_profiles(["a"])
