"""Atribución asistida por IA — endpoints admin (propuestas y revisión humana).

Se verifica el contrato con osap-storage: códigos 409/503 propagados sin disfrazarse de 403,
`reviewed_by` derivado del token (nunca del cuerpo) y errores de storage 5xx como 503.
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
ADMIN_USER_ID = "admin1"
ADMIN_HEADERS = {"Authorization": f"Bearer {TOKEN_ADMIN}"}


class _FakeAiClient(StorageComposerClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://127.0.0.1:1")
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def list_work_attribution_proposals(
        self, status_filter: str | None, limit: int, offset: int
    ) -> tuple[int, dict[str, object]]:
        self.calls.append(("list", (status_filter, limit, offset)))
        if offset == 999:
            return 500, {"detail": {"code": "DB_ERROR", "message": "table missing"}}
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
                    "role_name": "composer",
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
            return 404, {"detail": {"code": "NOT_FOUND", "message": "propuesta no encontrada"}}
        return 200, {
            "id": proposal_id,
            "work_id": 310455,
            "resolution": "identified",
            "person_match": "matched",
            "status": "pending",
            "evidence_json": "[]",
        }

    def propose_work_attribution(
        self, work_id: int, batch_id: str | None, force: bool
    ) -> tuple[int, dict[str, object]]:
        self.calls.append(("propose", (work_id, batch_id, force)))
        if work_id == 500:
            return 503, {"detail": {"code": "AI_NOT_CONFIGURED", "message": "IA no configurada"}}
        reused = not force
        return 200, {
            "proposal": {
                "id": 7 if force else 6,
                "work_id": work_id,
                "resolution": "unknown",
                "person_match": "not_applicable",
                "status": "pending",
            },
            "reused": reused,
        }

    def review_work_attribution_proposal(
        self, proposal_id: int, action: str, note: str | None, reviewed_by: str | None
    ) -> tuple[int, dict[str, object]]:
        self.calls.append(("review", (proposal_id, action, note, reviewed_by)))
        if proposal_id == 123:
            return 409, {
                "detail": {"code": "PROPOSAL_NOT_ASSIGNABLE", "message": "requiere persona resuelta"}
            }
        if proposal_id == 124:
            return 409, {
                "detail": {"code": "PROPOSAL_NOT_PENDING", "message": "la propuesta ya no está pendiente"}
            }
        if proposal_id == 125:
            return 500, {"detail": {"code": "DB_ERROR", "message": "audit table missing"}}
        status = {"accept": "accepted", "reject": "rejected", "uncertain": "uncertain"}[action]
        return 200, {"id": proposal_id, "status": status}


def _build(auth) -> tuple[TestClient, _FakeAiClient]:  # type: ignore[no-untyped-def]
    fake = _FakeAiClient()
    service = ComposersService(fake, auth)
    container = Container()
    container.set_authenticator(auth)
    container.set_composers(service)
    return TestClient(create_platform_app(container=container)), fake


def _user_client() -> TestClient:
    return _build(StaticTokenAuthenticator(TOKEN_USER, "u1", roles=("user",)))[0]


def _admin_client() -> TestClient:
    return _build(StaticTokenAuthenticator(TOKEN_ADMIN, ADMIN_USER_ID, roles=("user", "admin")))[0]


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
    data = resp.json()["data"]
    assert data["reused"] is True
    assert data["proposal"]["status"] == "pending"


def test_propose_force_reconsulta_y_pasa_force_a_storage() -> None:
    client, fake = _build(
        StaticTokenAuthenticator(TOKEN_ADMIN, ADMIN_USER_ID, roles=("user", "admin"))
    )
    resp = client.post(
        "/api/v1/admin/work-person-ai/propose/310455?force=true", headers=ADMIN_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["reused"] is False
    propose_calls = [call for call in fake.calls if call[0] == "propose"]
    assert propose_calls[0][1] == (310455, None, True)


def test_review_accept_200_y_usa_la_identidad_del_token() -> None:
    client = _admin_client()
    resp = client.post(
        "/api/v1/admin/work-person-ai/1/review",
        json={"action": "accept", "note": "ok", "reviewed_by": "otro-admin"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "accepted"


def test_reviewed_by_sale_del_token_no_del_cuerpo() -> None:
    client, fake = _build(
        StaticTokenAuthenticator(TOKEN_ADMIN, ADMIN_USER_ID, roles=("user", "admin"))
    )
    client.post(
        "/api/v1/admin/work-person-ai/1/review",
        json={"action": "accept", "reviewed_by": "otro-admin"},
        headers=ADMIN_HEADERS,
    )
    review_calls = [call for call in fake.calls if call[0] == "review"]
    assert review_calls[0][1][3] == ADMIN_USER_ID


def test_review_unresolved_409_conserva_el_mensaje() -> None:
    resp = _admin_client().post(
        "/api/v1/admin/work-person-ai/123/review", json={"action": "accept"}, headers=ADMIN_HEADERS
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PROPOSAL_NOT_ASSIGNABLE"
    assert "persona resuelta" in resp.json()["error"]["message"]


def test_review_no_pending_409() -> None:
    resp = _admin_client().post(
        "/api/v1/admin/work-person-ai/124/review", json={"action": "accept"}, headers=ADMIN_HEADERS
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PROPOSAL_NOT_PENDING"


def test_storage_5xx_se_propaga_como_503_y_no_como_403() -> None:
    resp = _admin_client().post(
        "/api/v1/admin/work-person-ai/125/review", json={"action": "accept"}, headers=ADMIN_HEADERS
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "ADMIN_SERVICE_UNAVAILABLE"
    assert "audit table missing" in resp.json()["error"]["message"]


def test_list_storage_5xx_503() -> None:
    resp = _admin_client().get(
        "/api/v1/admin/work-person-ai?status=pending&offset=999", headers=ADMIN_HEADERS
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "ADMIN_SERVICE_UNAVAILABLE"


def test_review_accion_invalida_422() -> None:
    resp = _admin_client().post(
        "/api/v1/admin/work-person-ai/1/review", json={"action": "explode"}, headers=ADMIN_HEADERS
    )
    assert resp.status_code == 422


def test_review_requires_token_401() -> None:
    resp = _user_client().post("/api/v1/admin/work-person-ai/1/review", json={"action": "accept"})
    assert resp.status_code == 401
