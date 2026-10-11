"""Tests de «Los amigos»: grupos, permisos, flujo editorial, autoría, orden y SSR.

Cubren las garantías exigidas: visitante lee lo publicado; un usuario sin autorización no
publica; el colaborador crea borradores; la publicación directa y la moderada; el admin de
un grupo no gestiona otro; revocar permisos bloquea nuevas operaciones sin borrar artículos;
la autoría original se conserva; la fecha del evento ordena; y los metadatos sociales se
sirven en HTML real.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.osap.api.http.context import HttpContext
from src.osap.api.http.seo import build_seo_router
from src.osap.application.amigos import AmigosError, AmigosService
from src.osap.infrastructure.state.op_store import _MemoryStore

_ADMIN = "admin-user"


def _service() -> tuple[AmigosService, _MemoryStore, dict[str, object]]:
    store = _MemoryStore()
    service = AmigosService(store)
    group = service.create_group(
        actor_user_id=_ADMIN,
        is_global_admin=True,
        name="Coral CTV",
        slug="ctv",
        editorial_mode="moderated",
    )
    return service, store, group


def _raw(service: AmigosService, group_id: str, **overrides: Any) -> dict[str, object]:
    payload: dict[str, Any] = {
        "title": "Concierto de Navidad",
        "event_date": "2026-12-20",
        "body": "Programa y crónica.\n\nSegundo párrafo.",
        "summary": "Crónica del concierto.",
    }
    payload.update(overrides)
    return service.create_article(
        actor_user_id=payload.pop("actor", "u1"),
        is_global_admin=payload.pop("is_global_admin", False),
        group_id=group_id,
        **payload,
    )


class TestGroupsAndMembership:
    def test_solo_admin_global_crea_grupos(self) -> None:
        store = _MemoryStore()
        service = AmigosService(store)
        with pytest.raises(AmigosError) as exc:
            service.create_group(actor_user_id="u1", is_global_admin=False, name="X")
        assert exc.value.status == 403

    def test_admin_del_grupo_no_designa_admins(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1", role="admin"
        )
        with pytest.raises(AmigosError) as exc:
            service.grant_member(
                actor_user_id="u1", is_global_admin=False, group_id=gid, user_id="u2", role="admin"
            )
        assert exc.value.status == 403
        # Un admin de grupo sí puede autorizar colaboradores.
        row = service.grant_member(
            actor_user_id="u1", is_global_admin=False, group_id=gid, user_id="u2",
            role="collaborator",
        )
        assert row["role"] == "collaborator"

    def test_admin_de_un_grupo_no_gestiona_otro(self) -> None:
        service, _store, group_a = _service()
        group_b = service.create_group(
            actor_user_id=_ADMIN, is_global_admin=True, name="Otra coral", slug="otra"
        )
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=str(group_a["id"]),
            user_id="u1", role="admin",
        )
        with pytest.raises(AmigosError) as exc:
            service.grant_member(
                actor_user_id="u1", is_global_admin=False, group_id=str(group_b["id"]),
                user_id="u2", role="collaborator",
            )
        assert exc.value.status == 403


class TestEditorialFlow:
    def test_usuario_sin_autorizacion_no_publica(self) -> None:
        service, _store, group = _service()
        with pytest.raises(AmigosError) as exc:
            _raw(service, str(group["id"]), action="draft")
        assert exc.value.status == 403

    def test_colaborador_crea_borrador_no_publico(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        article = _raw(service, gid, action="draft")
        assert article["status"] == "draft"
        assert service.get_public_article(str(article["id"])) is None

    def test_publicacion_directa(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.update_group(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, editorial_mode="direct"
        )
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        article = _raw(service, gid, action="publish")
        assert article["status"] == "published"
        assert service.get_public_article(str(article["id"])) is not None

    def test_moderada_queda_pendiente(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        article = _raw(service, gid, action="publish")
        assert article["status"] == "pending"
        assert service.get_public_article(str(article["id"])) is None
        public = service.list_group_articles(
            group_id=gid, include_non_public=False, actor_user_id=None
        )
        assert public["total"] == 0

    def test_aprobacion_publica(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        article = _raw(service, gid, action="publish")
        approved = service.approve_article(
            actor_user_id=_ADMIN, is_global_admin=True, article_id=str(article["id"])
        )
        assert approved["status"] == "published"
        assert service.get_public_article(str(article["id"])) is not None

    def test_admin_publica_directo_en_moderada(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1", role="admin"
        )
        article = _raw(service, gid, actor="u1", action="publish")
        assert article["status"] == "published"

    def test_cambio_de_modalidad_no_publica_pendientes(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        article = _raw(service, gid, action="publish")  # pending
        service.update_group(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, editorial_mode="direct"
        )
        # La decisión es explícita: pasar a `direct` NO publica retroactivamente.
        assert service.get_public_article(str(article["id"])) is None

    def test_retirar_oculta_sin_borrar(self) -> None:
        service, store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        article = _raw(service, gid, actor="u1", action="publish")
        service.approve_article(
            actor_user_id=_ADMIN, is_global_admin=True, article_id=str(article["id"])
        )
        service.withdraw_article(
            actor_user_id="u1", is_global_admin=False, article_id=str(article["id"])
        )
        assert service.get_public_article(str(article["id"])) is None
        assert store.get_amigos_article(str(article["id"])) is not None


class TestIntegrityAndOrder:
    def test_autor_original_se_conserva_tras_edicion_admin(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        article = _raw(service, gid, actor="u1", action="draft")
        updated = service.update_article(
            actor_user_id=_ADMIN, is_global_admin=True, article_id=str(article["id"]),
            title="Título corregido por el admin",
        )
        assert updated["author_user_id"] == "u1"
        assert updated["title"] == "Título corregido por el admin"

    def test_revocar_impide_nuevas_contribuciones(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        article = _raw(service, gid, actor="u1", action="publish")
        service.approve_article(
            actor_user_id=_ADMIN, is_global_admin=True, article_id=str(article["id"])
        )
        service.revoke_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        with pytest.raises(AmigosError) as exc:
            _raw(service, gid, actor="u1", action="draft")
        assert exc.value.status == 403
        # El artículo publicado NO se borra al revocar.
        assert service.get_public_article(str(article["id"])) is not None

    def test_orden_por_fecha_de_evento(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1", role="admin"
        )
        first = _raw(service, gid, actor="u1", action="publish", event_date="2026-01-10", title="A")
        second = _raw(service, gid, actor="u1", action="publish", event_date="2026-11-30", title="B")
        listing = service.list_group_articles(group_id=gid, include_non_public=False, actor_user_id=None)
        ids = [item["id"] for item in listing["items"]]  # type: ignore[union-attr]
        assert ids == [str(second["id"]), str(first["id"])]


class TestCoralDetails:
    def test_ficha_vacia_al_crear_y_actualizable(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        empty = service.get_coral_details(gid)
        assert empty is not None
        assert empty["formation_type"] is None
        assert empty["repertoire"] == []

        updated = service.update_coral_details(
            actor_user_id=_ADMIN,
            is_global_admin=True,
            group_id=gid,
            foundation_date="1985-03-01",
            locality="Valencia",
            region="Comunitat Valenciana",
            country_code="es",
            formation_type="mixed",
            member_count=42,
            website="https://example.org/ctv",
            public_email="info@example.org",
            director_label="Ana Pérez",
            linked_entity="Parroquia de San Juan",
            repertoire=["renacimiento", "barroco"],
            languages=["es", "la"],
        )
        assert updated["country_code"] == "ES"
        assert updated["member_count"] == 42
        assert updated["formation_type"] == "mixed"
        assert updated["repertoire"] == ["renacimiento", "barroco"]
        assert updated["languages"] == ["es", "la"]

    def test_actualizacion_parcial_de_facetas_conserva_la_otra(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.update_coral_details(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid,
            repertoire=["barroco"], languages=["es"],
        )
        service.update_coral_details(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid,
            repertoire=["renacimiento"],
        )
        row = service.get_coral_details(gid)
        assert row is not None
        assert row["repertoire"] == ["renacimiento"]
        assert row["languages"] == ["es"]

    def test_solo_admin_del_grupo_edita_la_ficha(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        with pytest.raises(AmigosError) as exc:
            service.update_coral_details(
                actor_user_id="u1", is_global_admin=False, group_id=gid, locality="X"
            )
        assert exc.value.status == 403
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u2", role="admin"
        )
        row = service.update_coral_details(
            actor_user_id="u2", is_global_admin=False, group_id=gid, locality="X"
        )
        assert row["locality"] == "X"

    def test_admin_de_un_grupo_no_edita_la_ficha_de_otro(self) -> None:
        service, _store, group_a = _service()
        group_b = service.create_group(
            actor_user_id=_ADMIN, is_global_admin=True, name="Otra coral", slug="otra"
        )
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=str(group_a["id"]),
            user_id="u1", role="admin",
        )
        with pytest.raises(AmigosError) as exc:
            service.update_coral_details(
                actor_user_id="u1", is_global_admin=False,
                group_id=str(group_b["id"]), locality="X",
            )
        assert exc.value.status == 403

    def test_validaciones_de_la_ficha(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        for kwargs, code in (
            ({"country_code": "ESP"}, "INVALID_COUNTRY"),
            ({"formation_type": "cuarteto"}, "INVALID_FORMATION_TYPE"),
            ({"member_count": -3}, "INVALID_MEMBER_COUNT"),
            ({"public_email": "no-es-email"}, "INVALID_EMAIL"),
            ({"foundation_date": "1985-13-40"}, "INVALID_DATE"),
            ({"website": "javascript:alert(1)"}, "INVALID_URL"),
        ):
            with pytest.raises(AmigosError) as exc:
                service.update_coral_details(
                    actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, **kwargs
                )
            assert exc.value.code == code, kwargs

    def test_indice_filtra_por_kind_y_excluye_otros_tipos(self) -> None:
        service, store, group = _service()
        store.add_amigos_group(
            group_id="orch1", slug="orch", name="Orquesta", kind="orquesta",
            description=None, image_url=None, editorial_mode="moderated", created_by=_ADMIN,
        )
        corals = service.list_groups(kind="coral")
        assert str(group["id"]) in [g["id"] for g in corals]
        assert "orch1" not in [g["id"] for g in corals]
        assert [g["id"] for g in store.list_amigos_groups(kind="orquesta")] == ["orch1"]
        with pytest.raises(AmigosError) as exc:
            service.list_groups(kind="no-soportado")
        assert exc.value.code == "INVALID_KIND"

    def test_grupo_de_otro_tipo_no_expone_ni_edita_ficha(self) -> None:
        service, store, _group = _service()
        store.add_amigos_group(
            group_id="orch1", slug="orch", name="Orquesta", kind="orquesta",
            description=None, image_url=None, editorial_mode="moderated", created_by=_ADMIN,
        )
        assert service.get_coral_details("orch1") is None
        with pytest.raises(AmigosError) as exc:
            service.update_coral_details(
                actor_user_id=_ADMIN, is_global_admin=True, group_id="orch1", locality="X"
            )
        assert exc.value.code == "NOT_A_CORAL"

    def test_multivalor_dedup_sin_distinguir_mayusculas(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        row = service.update_coral_details(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid,
            repertoire=["Barroco", "barroco", "BARROCO", "Clásico"],
            languages=["ES", "es", "la"],
        )
        assert row["repertoire"] == ["Barroco", "Clásico"]
        assert row["languages"] == ["ES", "la"]

    def test_lugares_de_actuacion(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        row = service.update_coral_details(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid,
            places=["Auditori de València", "Església de Sant Joan"],
        )
        assert row["places"] == ["Auditori de València", "Església de Sant Joan"]

    def test_disolver_grupo_conserva_articulos(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1", role="admin"
        )
        article = _raw(service, gid, actor="u1", action="publish")
        service.update_group(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, status="dissolved"
        )
        # Disolver no borra ni oculta el historial de artículos.
        assert service._store.get_amigos_article(str(article["id"])) is not None
        assert service.get_public_article(str(article["id"])) is not None


class TestGroupProfile:
    def test_campos_comunes_y_enlaces(self) -> None:
        store = _MemoryStore()
        service = AmigosService(store)
        group = service.create_group(
            actor_user_id=_ADMIN, is_global_admin=True, name="Coral CTV", slug="ctv",
            website="https://ctv.example.org", email="info@ctv.example.org",
            logo_url="https://cdn.example.org/logo.png",
            links=[
                {"kind": "facebook", "url": "https://facebook.com/ctv"},
                {"kind": "instagram", "url": "https://instagram.com/ctv"},
                {"kind": "other", "label": "YouTube", "url": "https://youtube.com/@ctv"},
            ],
        )
        gid = str(group["id"])
        row = service.get_group(gid)
        assert row is not None
        assert row["website"] == "https://ctv.example.org"
        assert row["email"] == "info@ctv.example.org"
        assert row["logo_url"] == "https://cdn.example.org/logo.png"
        links = store.list_amigos_group_links(gid)
        assert [x["kind"] for x in links] == ["facebook", "instagram", "other"]
        assert links[2]["label"] == "YouTube"

        service.update_group(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid,
            email="nuevo@ctv.example.org",
            links=[{"kind": "facebook", "url": "https://facebook.com/ctv2"}],
        )
        assert service.get_group(gid)["email"] == "nuevo@ctv.example.org"  # type: ignore[index]
        assert len(store.list_amigos_group_links(gid)) == 1

    def test_enlaces_invalidos(self) -> None:
        store = _MemoryStore()
        service = AmigosService(store)
        with pytest.raises(AmigosError) as bad_kind:
            service.create_group(
                actor_user_id=_ADMIN, is_global_admin=True, name="X",
                links=[{"kind": "tiktok", "url": "https://tiktok.com/x"}],
            )
        assert bad_kind.value.code == "INVALID_LINK_KIND"
        with pytest.raises(AmigosError) as bad_url:
            service.create_group(
                actor_user_id=_ADMIN, is_global_admin=True, name="Y",
                links=[{"kind": "other", "url": "javascript:alert(1)"}],
            )
        assert bad_url.value.code == "INVALID_URL"

    def test_email_invalido_en_grupo(self) -> None:
        store = _MemoryStore()
        service = AmigosService(store)
        with pytest.raises(AmigosError) as exc:
            service.create_group(
                actor_user_id=_ADMIN, is_global_admin=True, name="Z", email="no-email"
            )
        assert exc.value.code == "INVALID_EMAIL"


class TestValidation:
    def test_fecha_de_evento_imposible_rechazada(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1")
        with pytest.raises(AmigosError) as exc:
            _raw(service, gid, action="draft", event_date="2026-02-31")
        assert exc.value.code == "INVALID_EVENT_DATE"

    def test_fecha_de_evento_formato_no_iso_rechazada(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1")
        with pytest.raises(AmigosError) as exc:
            _raw(service, gid, action="draft", event_date="20/12/2026")
        assert exc.value.code == "INVALID_EVENT_DATE"


class TestMedia:
    def test_solo_youtube_para_videos(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1")
        with pytest.raises(AmigosError) as exc:
            _raw(
                service, gid, action="draft",
                media=[{"kind": "video", "url": "https://example.com/video.mp4"}],
            )
        assert exc.value.code == "INVALID_VIDEO_URL"

    def test_youtube_se_guarda_con_id_y_proveedor(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1")
        article = _raw(
            service, gid, action="draft",
            media=[{"kind": "video", "url": "https://youtu.be/dQw4w9WgXcQ", "caption": "Ensayo"}],
        )
        media = service._store.list_amigos_media(str(article["id"]))
        assert media[0]["provider"] == "youtube"
        assert media[0]["video_id"] == "dQw4w9WgXcQ"

    def test_foto_con_esquema_invalido_rechazada(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1")
        with pytest.raises(AmigosError) as exc:
            _raw(
                service, gid, action="draft",
                media=[{"kind": "photo", "url": "javascript:alert(1)"}],
            )
        assert exc.value.code == "INVALID_URL"


class TestEndpoints:
    def test_crear_requiere_login_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi
        from src.osap.domain.votes import UnauthenticatedError

        def fake(self: Any, *a: Any, **kw: Any) -> Any:
            raise UnauthenticatedError("login required")

        monkeypatch.setattr(PlatformApi, "amigos_create_article", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.post(
                "/api/v1/amigos/groups/g1/articles",
                json={"title": "T", "event_date": "2026-01-01", "body": "x"},
            )
        assert resp.status_code == 401

    def test_sin_autorizacion_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi

        def fake(self: Any, *a: Any, **kw: Any) -> Any:
            raise AmigosError(403, "FORBIDDEN", "No autorizado")

        monkeypatch.setattr(PlatformApi, "amigos_create_article", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.post(
                "/api/v1/amigos/groups/g1/articles",
                json={"title": "T", "event_date": "2026-01-01", "body": "x"},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"


_A_BASE = "https://app.openmusicrepository.com"
_GROUP = {
    "id": "g123",
    "slug": "ctv",
    "name": "Coral CTV",
    "kind": "coral",
    "description": "Coral de la Vila.",
    "image_url": None,
    "website": "https://ctv.example.org",
    "email": "info@ctv.example.org",
    "logo_url": "https://cdn.example.org/logo.png",
    "links": [
        {"kind": "facebook", "url": "https://facebook.com/ctv", "label": None},
        {"kind": "other", "url": "https://youtube.com/@ctv", "label": "YouTube"},
    ],
    "status": "active",
    "editorial_mode": "moderated",
    "coral": {
        "group_id": "g123",
        "foundation_date": "1985-03-01",
        "locality": "Valencia",
        "country_code": "ES",
        "formation_type": "mixed",
        "member_count": 42,
        "repertoire": ["renacimiento", "barroco"],
        "languages": ["es", "la"],
        "places": ["Auditori de València"],
    },
    "articles": [
        {
            "id": "a1",
            "title": "Concierto de Navidad",
            "event_date": "2026-12-20",
            "summary": "Crónica",
        }
    ],
}
_ARTICLE = {
    "id": "a1",
    "group_id": "g123",
    "group_slug": "ctv",
    "group_name": "Coral CTV",
    "title": "Concierto de Navidad",
    "slug": "concierto-de-navidad",
    "event_date": "2026-12-20",
    "summary": "Crónica del concierto",
    "body": "Primer párrafo.\n\nSegundo párrafo.",
    "cover_url": "https://cdn.example.com/cover.jpg",
    "published_at": "2026-12-21T10:00:00+00:00",
    "media": [
        {"kind": "video", "url": "https://youtu.be/dQw4w9WgXcQ", "video_id": "dQw4w9WgXcQ",
         "provider": "youtube", "caption": "Ensayo"},
    ],
}


class _FakeSeoApi:
    def seo_amigos_group(self, group_id: str) -> dict[str, object] | None:
        return _GROUP if group_id == "g123" else None

    def seo_amigos_article(self, article_id: str) -> dict[str, object] | None:
        return _ARTICLE if article_id == "a1" else None

    def seo_work(self, work_id: str | None) -> dict[str, object] | None:
        return None

    def seo_person(self, person_id: str) -> dict[str, object] | None:
        return None

    def seo_person_works(self, person_id: str, limit: int, offset: int) -> dict[str, object]:
        return {"items": [], "total": 0}


def _seo_client() -> TestClient:
    app = FastAPI()
    app.include_router(build_seo_router(HttpContext(api=_FakeSeoApi(), container=object())))  # type: ignore[arg-type]
    return TestClient(app)


@pytest.fixture(autouse=True)
def _fixed_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OSAP_PUBLIC_BASE_URL", _A_BASE)


class TestSeo:
    def test_articulo_sin_slug_redirige_al_canonico(self) -> None:
        client = _seo_client()
        resp = client.get("/amigos/articulo/a1", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["location"] == "/amigos/articulo/a1/concierto-de-navidad"

    def test_pagina_de_articulo_tiene_og_metadatos(self) -> None:
        client = _seo_client()
        resp = client.get("/amigos/articulo/a1/concierto-de-navidad")
        assert resp.status_code == 200
        assert "<h1>Concierto de Navidad</h1>" in resp.text
        assert '<meta property="og:title" content="Concierto de Navidad" />' in resp.text
        assert (
            f'<meta property="og:url" content="{_A_BASE}/amigos/articulo/a1/concierto-de-navidad" />'
            in resp.text
        )
        assert '<meta property="og:image" content="https://cdn.example.com/cover.jpg" />' in resp.text
        assert '<meta name="twitter:card" content="summary_large_image" />' in resp.text
        assert f'<link rel="canonical" href="{_A_BASE}/amigos/articulo/a1/concierto-de-navidad" />' in resp.text
        # El cuerpo se renderiza como texto, no HTML crudo.
        assert "Primer párrafo." in resp.text and "Segundo párrafo." in resp.text
        # El vídeo se incrusta desde el id validado (no desde HTML del usuario).
        assert "https://www.youtube.com/embed/dQw4w9WgXcQ" in resp.text

    def test_grupo_sin_slug_redirige_y_lista_articulos(self) -> None:
        client = _seo_client()
        resp = client.get("/amigos/corales/g123", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["location"] == "/amigos/corales/g123/ctv"
        page = client.get("/amigos/corales/g123/ctv")
        assert page.status_code == 200
        assert "<h1>Coral CTV</h1>" in page.text
        assert 'href="/amigos/articulo/a1/concierto-de-navidad"' in page.text
        # Ficha estructurada del tipo (coral) presente en la página pública.
        assert "Ficha" in page.text and "Valencia" in page.text and "ES" in page.text
        assert "renacimiento" in page.text and "barroco" in page.text
        assert "Lugares de actuación" in page.text and "Auditori" in page.text
        # Datos comunes del grupo: web, email, logo y redes.
        assert "https://ctv.example.org" in page.text
        assert "mailto:info@ctv.example.org" in page.text
        assert "https://cdn.example.org/logo.png" in page.text
        assert "https://facebook.com/ctv" in page.text and "YouTube" in page.text

    def test_articulo_no_publicado_404(self) -> None:
        client = _seo_client()
        resp = client.get("/amigos/articulo/nope/x")
        assert resp.status_code == 404
        assert "No encontrado" in resp.text

    def test_json_ld_es_article(self) -> None:
        client = _seo_client()
        html = client.get("/amigos/articulo/a1/concierto-de-navidad").text
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        assert match is not None
        import json

        payload = json.loads(match.group(1))
        node = next(n for n in payload["@graph"] if n["@type"] == "Article")
        assert node["headline"] == "Concierto de Navidad"
        assert node["datePublished"] == "2026-12-20"
