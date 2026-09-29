"""Atribución asistida por IA — endpoints admin (propuestas y revisión humana).

Sin IA configurada storage responde 503; osap-api lo propaga como 503 AI_NOT_CONFIGURED.
Aceptar una propuesta sin persona resuelta (409 en storage) se propaga como 409.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.osap.api.platform_app import create_platform_app
from src.osap.application.composers_service import ComposersService
from src.osap.bootstrap.container import Container
from src.osap.infrastructure.auth.token_authenticator import StaticTokenAuthenticator
from src.osap.infrastructure.storage.storage_composer_client import StorageComposerClient

TOKEN_USER = "tok-user"
TOKEN_ADMIN = "tok-admin"
ADMIN_HEADERS = {"Authorization": f"Bearer {TOKEN_ADMIN}"}


class _FakeAiClient(StorageComposerClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://127.0.0.1:1")
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def list_work_attribution_proposals(
        self, status_filter: str | None, limit: int, offset: int
    ) -> tuple[int, dict[str, object]]:
        self.calls.append(("list", (status_filter, limit, offset)))
        return 200, {
            "items": [
                {
                    "id": 1,
                    "work_id": 310455,
                    "resolution": "identified",
                    "person_match": "matched",
                    "candidate_person_id": "p1",
                    "candidate_name": "Louise Farrenc",
                    "role_id": 1,
                    "role_name": "Compositor/a",
                    "status": status_filter or "pending",
                    "confidence": 0.96,
                    "model": "fake",
                    "evidence_json": '[{"type": "source_metadata", "text": "PDMX"}]',
                }
            ],
            "total": 1,
        }

    def get_work_attribution_proposal(self, proposal_id: int) -> tuple[int, dict[str, object]]:
        if proposal_id == 999:
            return 404, {}
        return 200, {
            "id": proposal_id,
            "work_id": 310455,
            "resolution": "identified",
            "person_match": "matched",
            "status": "pending",
            "evidence_json": "[]",
        }

    def propose_work_attribution(self, work_id: int, batch_id: str | None) -> tuple[int, dict[str, object]]:
        if work_id == 500:
            return 503, {}
        return 200, {
            "id": 7,
            "work_id": work_id,
            "resolution": "unknown",
            "person_match": "not_applicable",
            "status": "pending",
        }

    def review_work_attribution_proposal(
        self, proposal_id: int, action: str, note: str | None, reviewed_by: str | None
    ) -> tuple[int, dict[str, object]]:
        self.calls.append(("review", (proposal_id, action, note, reviewed_by)))
        if proposal_id == 123:
            return 409, {}
        status = {"accept": "accepted", "reject": "rejected", "uncertain": "uncertain"}[action]
        return 200, {"id": proposal_id, "status": status}


def _build(auth) -> TestClient:  # type: ignore[no-untyped-def]
    service = ComposersService(_FakeAiClient(), auth)
    container = Container()
    container.set_authenticator(auth)
    container.set_composers(service)
    return TestClient(create_platform_app(container=container))


def _user_client() -> TestClient:
    return _build(StaticTokenAuthenticator(TOKEN_USER, "u1", roles=("user",)))


def _admin_client() -> TestClient:
    return _build(StaticTokenAuthenticator(TOKEN_ADMIN, "admin1", roles=("user", "admin")))


def test_list_requires_token_401() -> None:
    assert _user_client().get("/api/v1/admin/work-person-ai").status_code == 401


def test_list_non_admin_403() -> None:
    resp = _user_client().get(
        "/api/v1/admin/work-person-ai", headers={"Authorization": f"Bearer {TOKEN_USER}"}
    )
    assert resp.status_code == 403


def test_list_admin_200_con_items() -> None:
    resp = _admin_client().get(
        "/api/v1/admin/work-person-ai?status=pending&limit=10&offset=0", headers=ADMIN_HEADERS
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    item = data["items"][0]
    assert item["work_id"] == 310455
    assert item["person_match"] == "matched"
    assert item["candidate_person_id"] == "p1"


def test_detail_404() -> None:
    resp = _admin_client().get("/api/v1/admin/work-person-ai/999", headers=ADMIN_HEADERS)
    assert resp.status_code == 404


def test_detail_admin_200() -> None:
    resp = _admin_client().get("/api/v1/admin/work-person-ai/5", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == 5


def test_propose_sin_ia_configurada_503() -> None:
    resp = _admin_client().post("/api/v1/admin/work-person-ai/propose/500", headers=ADMIN_HEADERS)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "AI_NOT_CONFIGURED"


def test_propose_admin_200() -> None:
    resp = _admin_client().post("/api/v1/admin/work-person-ai/propose/310455", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "pending"


def test_review_accept_200() -> None:
    resp = _admin_client().post(
        "/api/v1/admin/work-person-ai/1/review",
        json={"action": "accept", "note": "ok", "reviewed_by": "admin1"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "accepted"


def test_review_unresolved_409() -> None:
    resp = _admin_client().post(
        "/api/v1/admin/work-person-ai/123/review", json={"action": "accept"}, headers=ADMIN_HEADERS
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PROPOSAL_NOT_ASSIGNABLE"


def test_review_accion_invalida_422() -> None:
    resp = _admin_client().post(
        "/api/v1/admin/work-person-ai/1/review", json={"action": "explode"}, headers=ADMIN_HEADERS
    )
    assert resp.status_code == 422


def test_review_requires_token_401() -> None:
    resp = _user_client().post("/api/v1/admin/work-person-ai/1/review", json={"action": "accept"})
    assert resp.status_code == 401
