"""V1 — Tests de los clientes de voto/obra contra osap-storage (contrato voto)."""

from __future__ import annotations

import json
import urllib.request

from src.osap.domain.votes import WorkVote
from src.osap.infrastructure.persistence.storage_vote_store import StorageVoteStore
from src.osap.infrastructure.storage.work_store import StorageWorkStore


class _FakeResponse:
    status = 200

    def __init__(self, body: bytes = b"{}") -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_storage_work_store_parses_nested_composer_id() -> None:
    captured: list[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request, timeout: int = 15) -> _FakeResponse:  # noqa: ARG001
        captured.append(request)
        return _FakeResponse(json.dumps({"work": {"id": 2, "composer_id": "a1e069ce-abc"}, "resources": []}).encode())

    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen  # type: ignore[assignment]
    try:
        store = StorageWorkStore(base_url="http://127.0.0.1:1")
        composer_id = store.composer_id_for("2")
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]

    assert captured[0].full_url.endswith("/api/v1/works/2")
    assert composer_id == "a1e069ce-abc"


def test_storage_vote_store_posts_to_works_votes_url() -> None:
    captured: list[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request, timeout: int = 15) -> _FakeResponse:  # noqa: ARG001
        captured.append(request)
        return _FakeResponse(b"{}")

    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen  # type: ignore[assignment]
    try:
        store = StorageVoteStore(base_url="http://127.0.0.1:1")
        vote = WorkVote(vote=5, work_id="2", user_id="u1")
        store.insert_vote(vote)
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]

    assert captured, "se esperaba una llamada a storage"
    assert captured[0].full_url.endswith("/api/v1/works/2/votes")
    body = json.loads(captured[0].data.decode())
    # El voto se envía con work_id en la URL; el body solo user_id + vote.
    assert body == {"user_id": "u1", "vote": 5}
