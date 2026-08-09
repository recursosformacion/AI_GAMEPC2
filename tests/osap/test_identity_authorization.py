"""V1 — Tests de identidad y autorización (Principal, token_use, admin, email_verified)."""

from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from src.osap.api.platform_app import create_platform_app
from src.osap.application.votes_service import VotesService
from src.osap.bootstrap.container import Container
from src.osap.domain.principal import ServicePrincipal, UserPrincipal
from src.osap.infrastructure.auth.service_token_provider import StaticServiceTokenProvider
from src.osap.infrastructure.auth.token_authenticator import (
    JwtAuthenticator,
    StaticServiceAuthenticator,
    StaticTokenAuthenticator,
)
from src.osap.infrastructure.persistence.memory_vote_store import MemoryVoteStore
from src.osap.infrastructure.storage.work_store import MemoryWorkStore

SEED = {"work-a": "comp-mozart"}


def _build(auth) -> TestClient:
    store = MemoryVoteStore()
    works = MemoryWorkStore(dict(SEED))
    service = VotesService(store, works, auth)
    container = Container()
    container.set_vote_store(store)
    container.set_work_store(works)
    container.set_authenticator(auth)
    container.set_votes(service)
    return TestClient(create_platform_app(container=container))


def _jwt(payload: dict) -> str:
    def enc(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        import base64

        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{enc({'alg':'none'})}.{enc(payload)}.{'sig'}"


# --- resolución de principal por token_use ----------------------------------


def test_token_use_user_resolves_user_principal() -> None:
    token = _jwt({"token_use": "user", "sub": "u1", "roles": ["user"], "email_verified": True})
    principal = JwtAuthenticator().resolve(f"Bearer {token}")
    assert isinstance(principal, UserPrincipal)
    assert principal.user_id == "u1"
    assert principal.has_role("user")


def test_token_use_service_resolves_service_principal() -> None:
    token = _jwt({"token_use": "service", "sub": "osap-api", "scope": "storage:read"})
    principal = JwtAuthenticator().resolve(token)
    assert isinstance(principal, ServicePrincipal)
    assert principal.service_id == "osap-api"
    assert principal.has_scope("storage:read")


def test_legacy_token_with_roles_resolves_user() -> None:
    token = _jwt({"sub": "u1", "roles": ["user"]})
    assert isinstance(JwtAuthenticator().resolve(token), UserPrincipal)


def test_legacy_token_with_client_id_resolves_service() -> None:
    token = _jwt({"client_id": "osap-api", "scope": "storage:read"})
    assert isinstance(JwtAuthenticator().resolve(token), ServicePrincipal)


def test_invalid_token_resolves_none() -> None:
    assert JwtAuthenticator().resolve("not-a-jwt") is None


# --- votar exige email_verified + rol user ----------------------------------


def test_anonymous_cannot_vote() -> None:
    client = _build(StaticTokenAuthenticator("tok", "u1"))
    assert client.post("/api/v1/works/work-a/vote", json={"vote": 5}).status_code == 401


def test_vote_requires_email_verified() -> None:
    client = _build(StaticTokenAuthenticator("tok", "u1", email_verified=False))
    resp = client.post("/api/v1/works/work-a/vote", json={"vote": 5}, headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 403


def test_vote_requires_user_role() -> None:
    client = _build(StaticTokenAuthenticator("tok", "u1", roles=("admin",)))
    resp = client.post("/api/v1/works/work-a/vote", json={"vote": 5}, headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 403


def test_verified_user_can_vote() -> None:
    client = _build(StaticTokenAuthenticator("tok", "u1", roles=("user",), email_verified=True))
    resp = client.post("/api/v1/works/work-a/vote", json={"vote": 5}, headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 201


# --- admin requiere role=admin ----------------------------------------------


def test_admin_requires_authentication() -> None:
    client = _build(StaticTokenAuthenticator("tok", "u1"))
    assert client.get("/api/v1/admin/votes").status_code == 401


def test_admin_rejects_plain_user() -> None:
    client = _build(StaticTokenAuthenticator("tok", "u1", roles=("user",)))
    resp = client.get("/api/v1/admin/votes", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 403


def test_admin_allows_admin_role() -> None:
    client = _build(StaticTokenAuthenticator("tok", "admin1", roles=("user", "admin")))
    resp = client.get("/api/v1/admin/votes", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200


def test_service_token_used_where_user_required_rejected() -> None:
    client = _build(StaticServiceAuthenticator("tok", "osap-api", ("storage:write",)))
    resp = client.post("/api/v1/works/work-a/vote", json={"vote": 5}, headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 401


# --- identidad de servicio --------------------------------------------------


def test_static_service_token_provider() -> None:
    provider = StaticServiceTokenProvider("svc-token")
    assert provider.token(("storage:read",)) == "svc-token"


def test_storage_vote_store_uses_least_privilege_scope() -> None:
    recorded: list[tuple[str, ...]] = []

    class Recording(StaticServiceTokenProvider):
        def token(self, scopes: tuple[str, ...]) -> str:
            recorded.append(scopes)
            return "svc-token"

    from src.osap.infrastructure.persistence.storage_vote_store import StorageVoteStore

    store = StorageVoteStore(base_url="http://127.0.0.1:1", token_provider=Recording("svc-token"))

    calls: list[urllib.request.Request] = []

    class FakeResponse:
        status = 201

        def read(self) -> bytes:
            return b"{}"

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    def fake_urlopen(request: urllib.request.Request, timeout: int = 15) -> FakeResponse:  # noqa: ARG001
        calls.append(request)
        return FakeResponse()

    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen  # type: ignore[assignment]
    try:
        from src.osap.domain.votes import WorkVote

        store.insert_vote(WorkVote(vote=5, work_id="work-a", user_id="u1"))
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]

    assert calls, "se esperaba una llamada a storage"
    assert calls[0].headers.get("Authorization") == "Bearer svc-token"
    assert recorded == [("storage:write",)]


def test_concurrency_duplicate_is_409() -> None:
    client = _build(StaticTokenAuthenticator("tok", "u1", roles=("user",)))
    codes: list[int] = []

    def fire() -> None:
        resp = client.post(
            "/api/v1/works/work-a/vote", json={"vote": 5}, headers={"Authorization": "Bearer tok"}
        )
        codes.append(resp.status_code)

    with ThreadPoolExecutor(max_workers=2) as ex:
        for f in [ex.submit(fire) for _ in range(2)]:
            f.result()
    assert sorted(codes) == [201, 409]
