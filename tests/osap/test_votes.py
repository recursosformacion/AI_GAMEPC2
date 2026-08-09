"""V1 — Tests de votos y estadísticas agregadas."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.osap.api.platform_app import create_platform_app
from src.osap.application.votes_service import VotesService
from src.osap.bootstrap.container import Container
from src.osap.domain.votes import (
    InvalidVoteError,
    VoteStats,
    WorkVote,
)
from src.osap.infrastructure.auth.token_authenticator import StaticTokenAuthenticator
from src.osap.infrastructure.persistence.memory_vote_store import MemoryVoteStore
from src.osap.infrastructure.storage.work_store import MemoryWorkStore

TOKEN = "token-alice"
USER_ID = "user-alice"

SEED = {
    "work-a": "comp-mozart",
    "work-b": "comp-mozart",
    "work-c": "comp-bach",
    "work-1": "comp-mozart",
    "work-2": "comp-mozart",
    "work-3": "comp-bach",
    "work-4": "comp-bach",
    "work-5": "comp-bach",
}


def _build() -> tuple[TestClient, VotesService, MemoryVoteStore, MemoryWorkStore]:
    store = MemoryVoteStore()
    works = MemoryWorkStore(dict(SEED))
    auth = StaticTokenAuthenticator(TOKEN, USER_ID)
    service = VotesService(store, works, auth)
    container = Container()
    container.set_vote_store(store)
    container.set_work_store(works)
    container.set_authenticator(auth)
    container.set_votes(service)
    app = create_platform_app(container=container)
    client = TestClient(app)
    return client, service, store, works


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


# --- autenticación / validación --------------------------------------------


def test_authenticated_user_can_vote() -> None:
    client, _, _, _ = _build()
    resp = client.post("/api/v1/works/work-a/vote", json={"vote": 5}, headers=_auth())
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["work_id"] == "work-a"
    assert data["vote"] == 5
    assert data["vote_day"] == datetime.now(UTC).date().isoformat()


def test_unauthenticated_cannot_vote() -> None:
    client, _, _, _ = _build()
    resp = client.post("/api/v1/works/work-a/vote", json={"vote": 5})
    assert resp.status_code == 401


def test_vote_scale_accepts_1_to_5() -> None:
    client, _, _, _ = _build()
    for i, v in enumerate([1, 2, 3, 4, 5], start=1):
        resp = client.post(f"/api/v1/works/work-{i}/vote", json={"vote": v}, headers=_auth())
        assert resp.status_code == 201, f"vote {v} should be accepted"


def test_vote_zero_rejected() -> None:
    client, _, _, _ = _build()
    resp = client.post("/api/v1/works/work-a/vote", json={"vote": 0}, headers=_auth())
    assert resp.status_code == 422


def test_vote_six_rejected() -> None:
    client, _, _, _ = _build()
    resp = client.post("/api/v1/works/work-a/vote", json={"vote": 6}, headers=_auth())
    assert resp.status_code == 422


# --- regla 1 voto por obra y día -------------------------------------------


def test_user_can_vote_multiple_works_same_day() -> None:
    client, _, _, _ = _build()
    assert client.post("/api/v1/works/work-a/vote", json={"vote": 4}, headers=_auth()).status_code == 201
    assert client.post("/api/v1/works/work-b/vote", json={"vote": 5}, headers=_auth()).status_code == 201


def test_user_cannot_vote_same_work_twice_same_day() -> None:
    client, _, _, _ = _build()
    assert client.post("/api/v1/works/work-a/vote", json={"vote": 4}, headers=_auth()).status_code == 201
    resp = client.post("/api/v1/works/work-a/vote", json={"vote": 5}, headers=_auth())
    assert resp.status_code == 409


def test_vote_day_computed_in_utc() -> None:
    _, service, _, _ = _build()
    vote = service.cast_vote(TOKEN, "work-a", 5)
    assert vote.vote_day == vote.voted_at.date().isoformat()
    assert vote.vote_day == datetime.now(UTC).date().isoformat()


def test_concurrent_requests_produce_one_vote() -> None:
    client, _, _, _ = _build()
    codes: list[int] = []

    def fire() -> None:
        resp = client.post("/api/v1/works/work-a/vote", json={"vote": 5}, headers=_auth())
        codes.append(resp.status_code)

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(fire) for _ in range(2)]
        for f in futures:
            f.result()
    assert sorted(codes) == [201, 409]


def test_work_not_found_returns_404() -> None:
    client, _, _, _ = _build()
    resp = client.post("/api/v1/works/does-not-exist/vote", json={"vote": 5}, headers=_auth())
    assert resp.status_code == 404


def test_client_cannot_send_user_id() -> None:
    client, _, _, _ = _build()
    resp = client.post(
        "/api/v1/works/work-a/vote", json={"vote": 5, "user_id": "evil", "vote_day": "1999-01-01"}, headers=_auth()
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["vote_day"] == datetime.now(UTC).date().isoformat()


# --- estadísticas de Work ---------------------------------------------------


def test_work_statistics() -> None:
    client, _, _, _ = _build()
    client.post("/api/v1/works/work-a/vote", json={"vote": 4}, headers=_auth())
    resp = client.get("/api/v1/works/work-a/statistics")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["work_id"] == "work-a"
    assert data["vote_count"] == 1
    assert data["vote_average"] == 4.0


def test_work_without_votes_has_zero_and_null() -> None:
    client, _, _, _ = _build()
    resp = client.get("/api/v1/works/work-c/statistics")
    data = resp.json()["data"]
    assert data["vote_count"] == 0
    assert data["vote_average"] is None


# --- estadísticas de compositor ---------------------------------------------


def test_composer_statistics() -> None:
    client, _, _, _ = _build()
    # work-a y work-b son de comp-mozart
    client.post("/api/v1/works/work-a/vote", json={"vote": 4}, headers=_auth())
    client.post("/api/v1/works/work-b/vote", json={"vote": 5}, headers=_auth())
    resp = client.get("/api/v1/composers/comp-mozart/statistics")
    data = resp.json()["data"]
    assert data["composer_id"] == "comp-mozart"
    assert data["vote_count"] == 2
    assert data["vote_average"] == 4.5  # (4+5)/2, no media de medias


def test_weighted_aggregation_not_average_of_averages() -> None:
    _, service, store, _ = _build()
    # Misma obra: 1 voto 5 y 1 voto 1 -> media 3. Otra obra del mismo compositor: 2 votos 5 -> media 5.
    store.insert_vote(WorkVote(vote=5, work_id="work-a", user_id="u1", composer_id="comp-mozart"))
    store.insert_vote(WorkVote(vote=1, work_id="work-a", user_id="u2", composer_id="comp-mozart"))
    store.insert_vote(WorkVote(vote=5, work_id="work-b", user_id="u1", composer_id="comp-mozart"))
    store.insert_vote(WorkVote(vote=5, work_id="work-b", user_id="u2", composer_id="comp-mozart"))
    stats = service.composer_statistics("comp-mozart")
    # Peso real: sum(5,1,5,5)=16 / 4 = 4.0 (una media de medias daría (3+5)/2=4.0 también aquí)
    assert stats.vote_count == 4
    assert stats.vote_sum == 16
    assert stats.vote_average == 4.0


def test_composer_without_votes() -> None:
    client, _, _, _ = _build()
    resp = client.get("/api/v1/composers/comp-bach/statistics")
    data = resp.json()["data"]
    assert data["vote_count"] == 0
    assert data["vote_average"] is None


# --- recálculo / idempotencia -----------------------------------------------


def test_storage_aggregation_idempotent_and_weighted() -> None:
    _, service, store, _ = _build()
    # Misma obra: 1 voto 5 y 1 voto 1. Otra obra del mismo compositor: 2 votos 5.
    store.insert_vote(WorkVote(vote=5, work_id="work-a", user_id="u1", composer_id="comp-mozart"))
    store.insert_vote(WorkVote(vote=1, work_id="work-a", user_id="u2", composer_id="comp-mozart"))
    store.insert_vote(WorkVote(vote=5, work_id="work-b", user_id="u1", composer_id="comp-mozart"))
    store.insert_vote(WorkVote(vote=5, work_id="work-b", user_id="u2", composer_id="comp-mozart"))
    work = store.work_statistics("work-a")
    assert work is not None and work.vote_count == 2 and work.vote_sum == 6 and work.vote_average == 3.0
    composer = service.composer_statistics("comp-mozart")
    # Peso real: sum(5,1,5,5)=16 / 4 = 4.0 (no media de medias).
    assert composer.vote_count == 4
    assert composer.vote_sum == 16
    assert composer.vote_average == 4.0
    # Idempotencia: releer no cambia el agregado.
    again = service.composer_statistics("comp-mozart")
    assert again.vote_count == composer.vote_count
    assert again.vote_average == composer.vote_average


def test_service_sends_current_composer_id_from_storage() -> None:
    _, service, store, _ = _build()
    # La identidad de compositor la proporciona Storage en el momento del voto.
    service.cast_vote(TOKEN, "work-c", 5)  # work-c -> comp-bach (SEED)
    assert store.work_statistics("work-c").vote_count == 1
    assert service.composer_statistics("comp-bach").vote_count == 1


# --- user.deleted -----------------------------------------------------------


def test_user_deleted_anonymizes_votes_and_stats_survive() -> None:
    _, service, store, _ = _build()
    service.cast_vote(TOKEN, "work-a", 4)
    service.cast_vote(TOKEN, "work-b", 5)
    before = service.composer_statistics("comp-mozart")

    result = service.handle_user_deleted(USER_ID)
    assert result["anonymized_works"] == 2

    after = service.composer_statistics("comp-mozart")
    # El agregado sobrevive a la anonimización.
    assert after.vote_count == before.vote_count == 2
    assert after.vote_average == before.vote_average == 4.5
    # El usuario ya no está asociado a los votos (sin PII).
    remaining = store.work_statistics("work-a")
    assert remaining is not None and remaining.vote_count == 1


# --- arquitectura: no acceso a BD de Auth/Storage ---------------------------


def test_no_direct_auth_db_access() -> None:
    import inspect

    from src.osap.application import votes_service as vs

    src = inspect.getsource(vs)
    for forbidden in ("users", "sessions", "tokens", "auth.db", "osap_auth"):
        assert forbidden not in src, f"votes_service accede a {forbidden!r}"


def test_no_direct_storage_db_access() -> None:
    import inspect

    from src.osap.application import votes_service as vs

    src = inspect.getsource(vs)
    for forbidden in (
        "composer_aliases",
        "merged_into",
        "storage.db",
        "FROM composers",
        "INSERT INTO composers",
        "CREATE TABLE composers",
    ):
        assert forbidden not in src, f"votes_service toca datos de Storage: {forbidden!r}"


def test_vote_stats_value_object() -> None:
    votes = [
        WorkVote(vote=5, work_id="w", user_id="u1"),
        WorkVote(vote=1, work_id="w", user_id="u2"),
        WorkVote(vote=4, work_id="w", user_id="u3"),
    ]
    stats = VoteStats.from_votes(votes)
    assert stats.vote_count == 3
    assert stats.vote_sum == 10
    assert stats.vote_average == pytest.approx(3.33)


def test_invalid_vote_raises_in_domain() -> None:
    with pytest.raises(InvalidVoteError):
        WorkVote(vote=0, work_id="w", user_id="u")
