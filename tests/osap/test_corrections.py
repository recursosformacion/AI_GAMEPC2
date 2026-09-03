"""Tests del circuito de soporte/correcciones (contacto y correcciones de catálogo)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.osap.application.corrections import CorrectionError, CorrectionService
from src.osap.infrastructure.state.op_store import _MemoryStore


class TestCorrectionService:
    def test_contacto_publico_se_almacena_pending(self) -> None:
        store = _MemoryStore()
        service = CorrectionService(store)
        row = service.submit(kind="contact", message="Hola, me gustaría contactar", contact_email="a@b.c")
        assert row["kind"] == "contact"
        assert row["status"] == "pending"
        assert store.get_correction(str(row["id"])) is not None

    def test_kind_invalido_422(self) -> None:
        service = CorrectionService(_MemoryStore())
        with pytest.raises(CorrectionError) as exc:
            service.submit(kind="billing", message="x")
        assert exc.value.status == 422
        assert exc.value.code == "INVALID_KIND"

    def test_mensaje_obligatorio_422(self) -> None:
        service = CorrectionService(_MemoryStore())
        with pytest.raises(CorrectionError) as exc:
            service.submit(kind="contact", message="   ")
        assert exc.value.code == "MESSAGE_REQUIRED"

    def test_correccion_requiere_entidad_422(self) -> None:
        service = CorrectionService(_MemoryStore())
        with pytest.raises(CorrectionError) as exc:
            service.submit(kind="work", message="título incorrecto", field="title")
        assert exc.value.code == "ENTITY_REQUIRED"

    def test_entidad_inexistente_404(self) -> None:
        service = CorrectionService(_MemoryStore(), exists=lambda _k, _e: False)
        with pytest.raises(CorrectionError) as exc:
            service.submit(
                kind="work",
                message="el título no es correcto",
                entity_id="999",
                entity_provider="omr",
                field="title",
                current_value="Mal",
                proposed_value="Bien",
            )
        assert exc.value.status == 404
        assert exc.value.code == "ENTITY_NOT_FOUND"

    def test_correccion_titulo_omr_por_defecto(self) -> None:
        store = _MemoryStore()
        service = CorrectionService(store, exists=lambda _k, _e: True)
        row = service.submit(
            kind="work",
            message="título incorrecto",
            entity_id="42",
            field="title",
            current_value="Mal",
            proposed_value="Bien",
        )
        assert row["entity_provider"] == "omr"
        assert row["status"] == "pending"

    def test_resolver_cambio_estado(self) -> None:
        store = _MemoryStore()
        service = CorrectionService(store)
        row = service.submit(kind="source", entity_id="imslp", message="descripción a mejorar")
        resolved = store.resolve_correction(str(row["id"]), "reviewed", "ok", "admin")
        assert resolved is not None
        assert resolved["status"] == "reviewed"
        assert store.pending_correction_count() == 0


class TestEndpointsCorrections:
    def test_contact_publico_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi

        def fake(self: Any, token: str | None, kind: str, message: str, **kw: Any) -> dict[str, object]:
            return {"id": "corr-1", "kind": "contact", "status": "pending", "created_at": "t"}

        monkeypatch.setattr(PlatformApi, "submit_correction", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.post(
                "/api/v1/contact", json={"kind": "contact", "message": "hola", "contact_email": "a@b.c"}
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "pending"

    def test_contact_mensaje_invalido_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi

        def fake(self: Any, token: str | None, kind: str, message: str, **kw: Any) -> dict[str, object]:
            raise CorrectionError(422, "MESSAGE_REQUIRED", "El mensaje es obligatorio")

        monkeypatch.setattr(PlatformApi, "submit_correction", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.post("/api/v1/contact", json={"kind": "contact", "message": ""})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "MESSAGE_REQUIRED"

    def test_correccion_requiere_login_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi
        from src.osap.domain.votes import UnauthenticatedError

        def fake(self: Any, token: str | None, kind: str, message: str, **kw: Any) -> dict[str, object]:
            raise UnauthenticatedError("login required")

        monkeypatch.setattr(PlatformApi, "submit_correction", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.post(
                "/api/v1/corrections",
                json={
                    "kind": "work",
                    "message": "x",
                    "entity_id": "42",
                    "entity_provider": "omr",
                    "field": "title",
                },
            )
        assert resp.status_code == 401

    def test_admin_lista_requiere_admin_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi
        from src.osap.domain.votes import ForbiddenError

        def fake(self: Any, token: str | None) -> list[dict[str, object]]:
            raise ForbiddenError("admin")

        monkeypatch.setattr(PlatformApi, "list_corrections", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.get("/api/v1/admin/corrections")
        assert resp.status_code == 403
