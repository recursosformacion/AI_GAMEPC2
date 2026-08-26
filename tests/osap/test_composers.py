"""V1 — Tests de compositores (consulta pública + fusión admin)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.osap.api.platform_app import create_platform_app
from src.osap.application.composers_service import ComposersService
from src.osap.bootstrap.container import Container
from src.osap.infrastructure.auth.token_authenticator import StaticTokenAuthenticator
from src.osap.infrastructure.storage.storage_composer_client import StorageComposerClient

TOKEN_USER = "tok-user"
TOKEN_ADMIN = "tok-admin"


class _FakeComposerClient(StorageComposerClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://127.0.0.1:1")

    def list_composers(
        self, q: str | None, limit: int, offset: int, review: str | None = None
    ) -> dict[str, object]:
        return {
            "items": [{"id": "comp-a", "name": "Mozart", "status": "active", "aliases_count": 3, "works_count": 264}],
            "total": 1,
        }

    def get_composer(self, composer_id: str) -> dict[str, object] | None:
        if composer_id == "missing":
            return None
        return {
            "id": composer_id,
            "name": "Mozart",
            "status": "active",
            "aliases": ["W. A. Mozart"],
            "works_count": 264,
            "creation_evidence": [
                {
                    "composer_id": composer_id,
                    "extracted_author": "W. A. Mozart",
                    "work_id": 2,
                    "work_title": "Ocean Man",
                    "provider": "musescore",
                    "resource_reference": "ext:abc",
                }
            ],
        }

    def composer_works(self, composer_id: str, limit: int, offset: int) -> dict[str, object]:
        return {"items": [{"work_id": 264, "title": "Ave verum", "composer_id": "comp-a"}], "total": 1}

    def merge_composers(self, target_id: str, source_ids: list[str]) -> tuple[int, dict[str, object]]:
        return 200, {
            "target_id": target_id,
            "sources_merged": source_ids,
            "aliases_transferred": 3,
            "works_moved": 2,
            "merge_operation_id": "op-1",
        }

    def create_composer(self, name: str) -> dict[str, object] | None:
        return {"id": "comp-new", "name": name, "status": "active", "aliases_count": 0, "works_count": 0}

    def review_composer(self, composer_id: str, review_status: str) -> tuple[int, dict[str, object]]:
        return 200, {
            "id": composer_id,
            "name": "Mozart",
            "status": "active",
            "aliases": [],
            "works_count": 264,
            "creation_evidence": [],
            "review_status": review_status,
        }

    def composer_review_stats(self) -> dict[str, int]:
        return {"total": 2, "correct": 1, "incorrect": 0, "reviewed": 1, "not_reviewed": 1}

    def storage_statistics(self) -> dict[str, int]:
        return {
            "archives": 12,
            "entries": 340,
            "files": 9800,
            "downloaded_tar": 9,
            "materialized": 300,
            "pending": 40,
            "bytes": 1_000_000_000,
        }


def _build(auth) -> TestClient:
    client = _FakeComposerClient()
    service = ComposersService(client, auth)
    container = Container()
    container.set_authenticator(auth)
    container.set_composers(service)
    return TestClient(create_platform_app(container=container))


def test_anonymous_can_list_composers() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_USER, "u1"))
    resp = client.get("/api/v1/composers")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Mozart"
    assert data["items"][0]["works_count"] == 264


def test_anonymous_can_get_composer_detail() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_USER, "u1"))
    resp = client.get("/api/v1/composers/comp-a")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["aliases"] == ["W. A. Mozart"]
    assert data["creation_evidence"][0]["work_title"] == "Ocean Man"
    assert data["creation_evidence"][0]["provider"] == "musescore"
    assert data["creation_evidence"][0]["extracted_author"] == "W. A. Mozart"


def test_unknown_composer_404() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_USER, "u1"))
    assert client.get("/api/v1/composers/missing").status_code == 404


def test_anonymous_can_get_composer_works() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_USER, "u1"))
    resp = client.get("/api/v1/composers/comp-a/works")
    assert resp.status_code == 200
    assert resp.json()["data"]["items"][0]["work_id"] == 264


def test_merge_without_token_401() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_USER, "u1"))
    resp = client.post("/api/v1/admin/composers/merge", json={"target_id": "comp-a", "sources": ["comp-b"]})
    assert resp.status_code == 401


def test_merge_non_admin_403() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_USER, "u1", roles=("user",)))
    resp = client.post(
        "/api/v1/admin/composers/merge",
        json={"target_id": "comp-a", "sources": ["comp-b"]},
        headers={"Authorization": f"Bearer {TOKEN_USER}"},
    )
    assert resp.status_code == 403


def test_merge_admin_200() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_ADMIN, "admin1", roles=("user", "admin")))
    resp = client.post(
        "/api/v1/admin/composers/merge",
        json={"target_id": "comp-a", "sources": ["comp-b"]},
        headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["target_id"] == "comp-a"
    assert data["sources_merged"] == ["comp-b"]


def test_premium_without_admin_has_no_admin_perms() -> None:
    # Un usuario "premium" sin role=admin NO puede fusionar (403).
    client = _build(StaticTokenAuthenticator(TOKEN_USER, "u1", roles=("user",)))
    resp = client.post(
        "/api/v1/admin/composers/merge",
        json={"target_id": "comp-a", "sources": ["comp-b"]},
        headers={"Authorization": f"Bearer {TOKEN_USER}"},
    )
    assert resp.status_code == 403


def test_create_composer_requires_admin() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_USER, "u1"))
    resp = client.post("/api/v1/admin/composers", json={"name": "New Composer"})
    assert resp.status_code == 401


def test_create_composer_admin_201() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_ADMIN, "admin1", roles=("user", "admin")))
    resp = client.post(
        "/api/v1/admin/composers",
        json={"name": "New Composer"},
        headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "New Composer"
    assert data["id"] == "comp-new"


def test_review_composer_requires_admin() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_USER, "u1"))
    resp = client.post(
        "/api/v1/admin/composers/comp-a/review", json={"review_status": "correct"}
    )
    assert resp.status_code == 401


def test_review_composer_admin_200() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_ADMIN, "admin1", roles=("user", "admin")))
    resp = client.post(
        "/api/v1/admin/composers/comp-a/review",
        json={"review_status": "correct"},
        headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["review_status"] == "correct"


def test_admin_overview_requires_admin() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_USER, "u1", roles=("user",)))
    resp = client.get("/api/v1/admin/overview", headers={"Authorization": f"Bearer {TOKEN_USER}"})
    assert resp.status_code == 403


def test_admin_overview_incluye_stats_de_storage() -> None:
    client = _build(StaticTokenAuthenticator(TOKEN_ADMIN, "admin1", roles=("user", "admin")))
    resp = client.get("/api/v1/admin/overview", headers={"Authorization": f"Bearer {TOKEN_ADMIN}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["composers"]["total"] == 3
    assert data["composers"]["correct"] == 1
    assert data["composers"]["reviewed"] == 2
    assert data["storage"]["archives"] == 12
    assert data["storage"]["entries"] == 340
    assert data["storage"]["materialized"] == 300
    assert data["storage"]["bytes"] == 1_000_000_000
