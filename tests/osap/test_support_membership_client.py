"""Cliente M2M de membership: parseo del contrato y fallo → SupportUnavailableError."""

from __future__ import annotations

import pytest
import requests

from src.osap.application.reconcile_membership import SupportUnavailableError
from src.osap.infrastructure.auth.service_token_provider import StaticServiceTokenProvider
from src.osap.infrastructure.support import membership_client as mc
from src.osap.infrastructure.support.membership_client import SupportMembershipClient


class _Resp:
    def __init__(self, status: int, doc: object) -> None:
        self.status_code = status
        self._doc = doc

    def json(self) -> object:
        if self._doc is None:
            raise ValueError("no json")
        return self._doc


def _client(monkeypatch, *, resp: object = None, exc: Exception | None = None) -> SupportMembershipClient:
    def _get(*a: object, **k: object) -> object:
        if exc is not None:
            raise exc
        return resp

    monkeypatch.setattr(mc.requests, "get", _get)
    return SupportMembershipClient(
        base_url="http://support", token_provider=StaticServiceTokenProvider("tok")
    )


def test_parsea_membresia_activa(monkeypatch) -> None:
    resp = _Resp(200, {"active": True, "tier": "donor", "valid_from": "2026-01-01",
                       "valid_until": "2026-12-31", "source": "stripe"})
    snap = _client(monkeypatch, resp=resp).fetch("u1")
    assert snap.active is True
    assert snap.tier == "donor"
    assert snap.source == "stripe"
    assert str(snap.valid_until)[:10] == "2026-12-31"


def test_parsea_sin_membresia(monkeypatch) -> None:
    resp = _Resp(200, {"active": False, "tier": None, "valid_from": None,
                       "valid_until": None, "source": None})
    snap = _client(monkeypatch, resp=resp).fetch("u1")
    assert snap.active is False
    assert snap.tier is None


@pytest.mark.parametrize("status", [401, 403, 500])
def test_http_no_200_es_unavailable(monkeypatch, status: int) -> None:
    with pytest.raises(SupportUnavailableError):
        _client(monkeypatch, resp=_Resp(status, {})).fetch("u1")


def test_error_de_red_es_unavailable(monkeypatch) -> None:
    with pytest.raises(SupportUnavailableError):
        _client(monkeypatch, exc=requests.RequestException("timeout")).fetch("u1")


def test_token_provider_falla_es_unavailable(monkeypatch) -> None:
    class _Bad:
        def token(self, scopes: tuple[str, ...]) -> str:
            raise RuntimeError("auth caido")

    client = SupportMembershipClient(base_url="http://support", token_provider=_Bad())
    with pytest.raises(SupportUnavailableError):
        client.fetch("u1")
