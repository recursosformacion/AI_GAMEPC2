"""Tests del circuito de aportaciones (contributions): add_resource, ciclo de vida y revisión."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.osap.api.contracts import ContributionRead
from src.osap.application.contributions import ContributionError, ContributionService
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError
from src.osap.infrastructure.state.op_store import _MemoryStore


def _service() -> ContributionService:
    return ContributionService(_MemoryStore())


def _store_service() -> tuple[ContributionService, _MemoryStore]:
    store = _MemoryStore()
    return ContributionService(store), store


def _create(service: ContributionService, *, actor: str = "u-1", target_id: str = "rep-1", relations=None):
    return service.create(
        actor_user_id=actor,
        operation="add_resource",
        target_kind="representation",
        target_id=target_id,
        declared_source=None,
        relations=relations or [],
        representation_exists=lambda rid: rid == "rep-1",
    )


class TestContributionService:
    def test_crear_add_resource(self) -> None:
        service, store = _store_service()
        row = _create(service)
        assert row["operation"] == "add_resource"
        assert row["target_kind"] == "representation"
        assert row["target_id"] == "rep-1"
        assert row["status"] == "draft"
        events = store.list_contribution_events(int(str(row["id"])))
        assert [e["event_type"] for e in events] == ["created"]

    def test_representacion_inexistente_404(self) -> None:
        service = _service()
        with pytest.raises(ContributionError) as exc:
            _create(service, target_id="nope")
        assert exc.value.status == 404
        assert exc.value.code == "REPRESENTATION_NOT_FOUND"

    def test_operacion_no_soportada_422(self) -> None:
        service = _service()
        with pytest.raises(ContributionError) as exc:
            service.create(
                actor_user_id="u-1",
                operation="create_work",
                target_kind="work",
                target_id="w-1",
                declared_source=None,
                relations=[],
                representation_exists=lambda _r: True,
            )
        assert exc.value.code == "UNSUPPORTED_OPERATION"

    def test_target_obligatorio(self) -> None:
        service = _service()
        with pytest.raises(ContributionError) as exc:
            _create(service, target_id="")
        assert exc.value.code == "TARGET_REQUIRED"

    def test_relaciones_multiples_y_codigos(self) -> None:
        service, store = _store_service()
        row = _create(
            service,
            relations=[
                {"relation_kind": "musical", "relation_code": "arranger", "person_name": "Juan"},
                {"relation_kind": "musical", "relation_code": "transcriber", "person_name": "Juan"},
                {"relation_kind": "contribution", "relation_code": "propietario_comparte"},
            ],
        )
        rels = store.list_contribution_relations(int(str(row["id"])))
        assert len(rels) == 3
        assert {r["validation_status"] for r in rels} == {"pending"}
        assert {r["materialized"] for r in rels} == {0}

    def test_relacion_aportacion_invalida(self) -> None:
        service = _service()
        with pytest.raises(ContributionError) as exc:
            _create(service, relations=[{"relation_kind": "contribution", "relation_code": "inventado"}])
        assert exc.value.code == "INVALID_RELATION_CODE"

    def test_adjuntar_artifact(self) -> None:
        service, store = _store_service()
        row = _create(service)
        updated = service.attach_artifact(
            actor_user_id="u-1", contribution_id=int(str(row["id"])), file_id=42, kind="score", is_admin=False
        )
        assert int(str(row["id"])) == int(str(updated["id"]))
        assert [a["file_id"] for a in store.list_contribution_artifacts(int(str(row["id"])))] == [42]

    def test_artifact_duplicado_409(self) -> None:
        service = _service()
        row = _create(service)
        cid = int(str(row["id"]))
        service.attach_artifact(actor_user_id="u-1", contribution_id=cid, file_id=42, kind=None, is_admin=False)
        with pytest.raises(ContributionError) as exc:
            service.attach_artifact(actor_user_id="u-1", contribution_id=cid, file_id=42, kind=None, is_admin=False)
        assert exc.value.code == "ARTIFACT_DUPLICATE"

    def test_attachment_ajeno_403(self) -> None:
        service = _service()
        row = _create(service, actor="u-1")
        with pytest.raises(ContributionError) as exc:
            service.attach_artifact(
                actor_user_id="u-2", contribution_id=int(str(row["id"])), file_id=1, kind=None, is_admin=False
            )
        assert exc.value.status == 403

    def test_get_ajena_devuelve_none(self) -> None:
        service = _service()
        row = _create(service, actor="u-1")
        assert service.get(actor_user_id="u-2", contribution_id=int(str(row["id"])), is_admin=False) is None
        assert service.get(actor_user_id="u-1", contribution_id=int(str(row["id"])), is_admin=False) is not None

    def test_submit_requiere_artifact(self) -> None:
        service = _service()
        row = _create(service)
        with pytest.raises(ContributionError) as exc:
            service.submit(actor_user_id="u-1", contribution_id=int(str(row["id"])), is_admin=False)
        assert exc.value.code == "ARTIFACT_REQUIRED"

    def test_submit_ok(self) -> None:
        service = _service()
        row = _create(service)
        cid = int(str(row["id"]))
        service.attach_artifact(actor_user_id="u-1", contribution_id=cid, file_id=7, kind=None, is_admin=False)
        updated = service.submit(actor_user_id="u-1", contribution_id=cid, is_admin=False)
        assert updated["status"] == "submitted"

    def test_transicion_invalida_409(self) -> None:
        service = _service()
        row = _create(service)
        # accept solo vale desde in_review
        with pytest.raises(ContributionError) as exc:
            service.review(contribution_id=int(str(row["id"])), action="accept", reviewer="admin", note="")
        assert exc.value.code == "INVALID_TRANSITION"

    def test_ciclo_completo_accept(self) -> None:
        service, store = _store_service()
        row = _create(service)
        cid = int(str(row["id"]))
        service.attach_artifact(actor_user_id="u-1", contribution_id=cid, file_id=7, kind=None, is_admin=False)
        service.submit(actor_user_id="u-1", contribution_id=cid, is_admin=False)
        in_review = service.review(contribution_id=cid, action="in_review", reviewer="admin", note="")
        assert in_review["status"] == "in_review"
        accepted = service.review(contribution_id=cid, action="accept", reviewer="admin", note="ok")
        assert accepted["status"] == "accepted"
        assert accepted["reviewed_by"] == "admin"
        # accepted NO materializa nada
        assert all(r["materialized"] == 0 for r in store.list_contribution_relations(cid))

    def test_rechazo(self) -> None:
        service = _service()
        row = _create(service)
        cid = int(str(row["id"]))
        service.attach_artifact(actor_user_id="u-1", contribution_id=cid, file_id=7, kind=None, is_admin=False)
        service.submit(actor_user_id="u-1", contribution_id=cid, is_admin=False)
        service.review(contribution_id=cid, action="in_review", reviewer="admin", note="")
        rejected = service.review(contribution_id=cid, action="reject", reviewer="admin", note="no")
        assert rejected["status"] == "rejected"

    def test_retirada(self) -> None:
        service, store = _store_service()
        row = _create(service)
        withdrawn = service.withdraw(actor_user_id="u-1", contribution_id=int(str(row["id"])), is_admin=False)
        assert withdrawn["status"] == "withdrawn"
        assert store.get_contribution(int(str(row["id"])))["status"] == "withdrawn"

    def test_independencia_estado_relacion(self) -> None:
        service, store = _store_service()
        row = _create(service, relations=[{"relation_kind": "musical", "relation_code": "arranger"}])
        cid = int(str(row["id"]))
        rel_id = int(str(store.list_contribution_relations(cid)[0]["id"]))
        service.attach_artifact(actor_user_id="u-1", contribution_id=cid, file_id=7, kind=None, is_admin=False)
        service.submit(actor_user_id="u-1", contribution_id=cid, is_admin=False)
        service.review(contribution_id=cid, action="in_review", reviewer="admin", note="")
        accepted = service.review(contribution_id=cid, action="accept", reviewer="admin", note="")
        assert accepted["status"] == "accepted"
        # La relación sigue pendiente tras aceptar la aportación.
        assert store.list_contribution_relations(cid)[0]["validation_status"] == "pending"
        # Y se valida por separado.
        service.review_relation(contribution_id=cid, relation_id=rel_id, action="reject", reviewer="admin", note="no")
        assert store.list_contribution_relations(cid)[0]["validation_status"] == "rejected"

    def test_eventos_append_only(self) -> None:
        service, store = _store_service()
        row = _create(service)
        cid = int(str(row["id"]))
        service.attach_artifact(actor_user_id="u-1", contribution_id=cid, file_id=7, kind=None, is_admin=False)
        service.submit(actor_user_id="u-1", contribution_id=cid, is_admin=False)
        events = [e["event_type"] for e in store.list_contribution_events(cid)]
        assert events == ["created", "artifact_added", "submitted"]

    def test_listado_mio_y_paginacion(self) -> None:
        service = _service()
        for _ in range(3):
            _create(service, actor="u-1")
        rows, total = service.list_mine(actor_user_id="u-1", limit=2, offset=0)
        assert total == 3 and len(rows) == 2


class TestContributionEndpoints:
    def test_crear_requiere_login_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi

        def fake(self: Any, *a: Any, **kw: Any) -> Any:
            raise UnauthenticatedError("login required")

        monkeypatch.setattr(PlatformApi, "create_contribution", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.post(
                "/api/v1/contributions",
                json={"operation": "add_resource", "target_kind": "representation", "target_id": "rep-1"},
            )
        assert resp.status_code == 401

    def test_crear_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi

        def fake(self: Any, *a: Any, **kw: Any) -> ContributionRead:
            return ContributionRead(
                id=1, actor_user_id="u-1", operation="add_resource", target_kind="representation",
                target_id="rep-1", declared_source=None, status="draft",
                reviewed_by=None, reviewed_at=None, review_note=None,
                created_at="t", updated_at="t", relations=[], artifacts=[],
            )

        monkeypatch.setattr(PlatformApi, "create_contribution", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.post(
                "/api/v1/contributions",
                json={"operation": "add_resource", "target_kind": "representation", "target_id": "rep-1"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "draft"

    def test_crear_validacion_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi

        def fake(self: Any, *a: Any, **kw: Any) -> Any:
            raise ContributionError(422, "TARGET_REQUIRED", "target_id es obligatorio")

        monkeypatch.setattr(PlatformApi, "create_contribution", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.post(
                "/api/v1/contributions",
                json={"operation": "add_resource", "target_kind": "representation"},
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "TARGET_REQUIRED"

    def test_admin_lista_requiere_admin_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi

        def fake(self: Any, *a: Any, **kw: Any) -> Any:
            raise ForbiddenError("admin")

        monkeypatch.setattr(PlatformApi, "list_contributions_admin", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.get("/api/v1/admin/contributions")
        assert resp.status_code == 403
