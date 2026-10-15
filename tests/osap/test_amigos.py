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

    def test_published_at_con_formato_datetime_compatible_mysql(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.grant_member(
            actor_user_id=_ADMIN, is_global_admin=True, group_id=gid, user_id="u1"
        )
        article = _raw(service, gid, action="publish")  # queda pending (moderada)
        approved = service.approve_article(
            actor_user_id=_ADMIN, is_global_admin=True, article_id=str(article["id"])
        )
        published_at = approved.get("published_at")
        assert isinstance(published_at, str)
        # MySQL DATETIME no admite 'T' ni offset; debe ser "AAAA-MM-DD HH:MM:SS[.ffffff]".
        assert "T" not in published_at and "+" not in published_at
        assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", published_at) is not None

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


class TestUploads:
    def test_autorizacion_y_validacion(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        with pytest.raises(AmigosError) as exc:
            service.authorize_upload(group_id=gid, actor_user_id="u1", is_global_admin=False)
        assert exc.value.status == 403
        service.authorize_upload(group_id=gid, actor_user_id=_ADMIN, is_global_admin=True)
        assert service.validate_upload(
            name="logo.png", mime_type="image/png", size_bytes=10
        ) == ("logo.png", "image/png")
        for mime, size, code in (
            ("text/plain", 10, "INVALID_IMAGE_TYPE"),
            ("image/png", 0, "EMPTY_UPLOAD"),
            ("image/png", 10**9, "IMAGE_TOO_LARGE"),
        ):
            with pytest.raises(AmigosError) as exc:
                service.validate_upload(name="x", mime_type=mime, size_bytes=size)
            assert exc.value.code == code

    def test_registro_y_lectura(self) -> None:
        service, _store, group = _service()
        gid = str(group["id"])
        service.record_upload(
            group_id=gid, file_id=42, mime_type="image/png", size_bytes=123,
            actor_user_id=_ADMIN,
        )
        rec = service.get_upload(42)
        assert rec is not None and rec["mime_type"] == "image/png" and rec["group_id"] == gid
        assert service.get_upload(999999) is None


class TestEvents:
    def test_gestion_reservada_a_admin_global(self) -> None:
        service = AmigosService(_MemoryStore())
        with pytest.raises(AmigosError) as exc:
            service.create_actuacion(
                actor_user_id="u1", is_global_admin=False,
                data={"title": "X", "starts_on": "2099-05-01"}, action="draft",
            )
        assert exc.value.status == 403

    def test_alta_publicacion_y_listado(self) -> None:
        service = AmigosService(_MemoryStore())
        draft = service.create_actuacion(
            actor_user_id=_ADMIN, is_global_admin=True,
            data={"title": "Encuentro Coral", "starts_on": "2099-05-10",
                  "starts_at": "18:30", "kind": "meeting", "locality": "Barcelona"},
            action="draft",
        )
        assert draft["editorial_status"] == "draft"
        assert service.get_public_actuacion(str(draft["id"])) is None
        published = service.create_actuacion(
            actor_user_id=_ADMIN, is_global_admin=True,
            data={"title": "Concierto", "starts_on": "2099-04-01"}, action="publish",
        )
        assert published["editorial_status"] == "published"
        listing = service.list_actuaciones(public_only=True)
        assert listing["total"] == 1
        ids = [e["id"] for e in listing["items"]]  # type: ignore[union-attr]
        assert str(published["id"]) in ids and str(draft["id"]) not in ids

    def test_validaciones_y_participantes(self) -> None:
        service = AmigosService(_MemoryStore())
        group = service.create_group(
            actor_user_id=_ADMIN, is_global_admin=True, name="Coral CTV", slug="ctv"
        )
        with pytest.raises(AmigosError) as e1:
            service.create_actuacion(
                actor_user_id=_ADMIN, is_global_admin=True,
                data={"starts_on": "2099-05-01"}, action="draft",
            )
        assert e1.value.code == "TITLE_REQUIRED"
        with pytest.raises(AmigosError) as e2:
            service.create_actuacion(
                actor_user_id=_ADMIN, is_global_admin=True, data={"title": "X"}, action="draft"
            )
        assert e2.value.code == "INVALID_START"
        with pytest.raises(AmigosError) as e3:
            service.create_actuacion(
                actor_user_id=_ADMIN, is_global_admin=True,
                data={"title": "X", "starts_on": "2099-05-01", "kind": "nope"}, action="draft",
            )
        assert e3.value.code == "INVALID_KIND"
        with pytest.raises(AmigosError) as e4:
            service.create_actuacion(
                actor_user_id=_ADMIN, is_global_admin=True,
                data={"title": "X", "starts_on": "2099-05-01", "groups": [{"group_id": "nope"}]},
                action="draft",
            )
        assert e4.value.code == "INVALID_GROUP"
        event = service.create_actuacion(
            actor_user_id=_ADMIN, is_global_admin=True,
            data={"title": "Encuentro", "starts_on": "2099-05-01",
                  "groups": [{"group_id": str(group["id"]), "role": "participant"}]},
            action="publish",
        )
        assert event["groups"][0]["group_id"] == str(group["id"])  # type: ignore[index]
        assert service.list_actuaciones(
            public_only=True, group_id=str(group["id"])
        )["total"] == 1

    def test_cambio_de_estado_editorial(self) -> None:
        service = AmigosService(_MemoryStore())
        event = service.create_actuacion(
            actor_user_id=_ADMIN, is_global_admin=True,
            data={"title": "Taller", "starts_on": "2099-06-01"}, action="draft",
        )
        published = service.set_actuacion_editorial(
            actor_user_id=_ADMIN, is_global_admin=True,
            actuacion_id=str(event["id"]), editorial_status="published",
        )
        assert published["editorial_status"] == "published"
        assert service.get_public_actuacion(str(event["id"])) is not None


    def test_peso_ordena_desc_y_excluye_pasados(self) -> None:
        service = AmigosService(_MemoryStore())
        low = service.create_actuacion(
            actor_user_id=_ADMIN, is_global_admin=True,
            data={"title": "Baja", "starts_on": "2099-06-01", "weight": 2}, action="publish",
        )
        high = service.create_actuacion(
            actor_user_id=_ADMIN, is_global_admin=True,
            data={"title": "Alta", "starts_on": "2099-07-01", "weight": 9}, action="publish",
        )
        service.create_actuacion(
            actor_user_id=_ADMIN, is_global_admin=True,
            data={"title": "Pasada", "starts_on": "2000-01-01", "weight": 9}, action="publish",
        )
        listing = service.list_actuaciones(public_only=True)
        assert [e["id"] for e in listing["items"]] == [str(high["id"]), str(low["id"])]  # type: ignore[union-attr]
        with pytest.raises(AmigosError) as exc:
            service.create_actuacion(
                actor_user_id=_ADMIN, is_global_admin=True,
                data={"title": "X", "starts_on": "2099-06-01", "weight": 10}, action="draft",
            )
        assert exc.value.code == "INVALID_WEIGHT"

    def test_contadores_de_anuncio(self) -> None:
        service = AmigosService(_MemoryStore())
        event = service.create_actuacion(
            actor_user_id=_ADMIN, is_global_admin=True,
            data={"title": "E", "starts_on": "2099-06-01"}, action="publish",
        )
        assert service.record_event_counter(str(event["id"]), "view") == 1
        assert service.record_event_counter(str(event["id"]), "view") == 2
        assert service.record_event_counter(str(event["id"]), "expand") == 1
        assert service.record_event_counter(str(event["id"]), "buy") == 1
        draft = service.create_actuacion(
            actor_user_id=_ADMIN, is_global_admin=True,
            data={"title": "D", "starts_on": "2099-06-01"}, action="draft",
        )
        assert service.record_event_counter(str(draft["id"]), "view") is None
        with pytest.raises(AmigosError):
            service.record_event_counter(str(event["id"]), "nope")


    def test_mios_y_permisos_y_edicion_solo_del_propio(self) -> None:
        service = AmigosService(_MemoryStore())
        service.grant_authorization(
            actor_user_id=_ADMIN, is_global_admin=True, user_id="u1", scope="events"
        )
        own = service.create_actuacion(
            actor_user_id="u1", is_global_admin=False,
            data={"title": "Mío", "starts_on": "2099-06-01"}, action="draft",
        )
        other = service.create_actuacion(
            actor_user_id=_ADMIN, is_global_admin=True,
            data={"title": "Otro", "starts_on": "2099-06-01"}, action="draft",
        )
        mine = service.list_my_actuaciones(actor_user_id="u1", is_global_admin=False)
        assert mine["total"] == 1 and mine["items"][0]["id"] == str(own["id"])  # type: ignore[union-attr]
        with pytest.raises(AmigosError) as exc:
            service.update_actuacion(
                actor_user_id="u1", is_global_admin=False, actuacion_id=str(other["id"]),
                data={"title": "X"},
            )
        assert exc.value.status == 403
        perms = service.my_permissions(actor_user_id="u1", is_global_admin=False)
        assert perms["events"] is True and perms["blog"] is False


class TestAuthorizationsAndBlog:
    def test_autorizacion_solo_admin_global(self) -> None:
        service = AmigosService(_MemoryStore())
        with pytest.raises(AmigosError) as exc:
            service.grant_authorization(
                actor_user_id="u1", is_global_admin=False, user_id="u2", scope="blog"
            )
        assert exc.value.status == 403
        row = service.grant_authorization(
            actor_user_id=_ADMIN, is_global_admin=True, user_id="u2", scope="blog"
        )
        assert row["scope"] == "blog" and row["direct_publish"] is False

    def test_blog_autor_pendiente_y_aprobacion(self) -> None:
        service = AmigosService(_MemoryStore())
        service.grant_authorization(
            actor_user_id=_ADMIN, is_global_admin=True, user_id="author", scope="blog"
        )
        article = service.create_general_article(
            actor_user_id="author", is_global_admin=False, title="Noticia coral",
            event_date="2026-03-01", body="Texto.", action="publish",
        )
        assert article["status"] == "pending"
        assert article["group_id"] is None
        assert service.get_public_general_article(str(article["id"])) is None
        with pytest.raises(AmigosError) as exc:
            service.create_general_article(
                actor_user_id="stranger", is_global_admin=False, title="X",
                event_date="2026-03-01", body="y", action="draft",
            )
        assert exc.value.status == 403
        approved = service.approve_general_article(
            actor_user_id=_ADMIN, is_global_admin=True, article_id=str(article["id"])
        )
        assert approved["status"] == "published"
        assert service.get_public_general_article(str(article["id"])) is not None
        assert service.list_blog_articles(public_only=True)["total"] == 1

    def test_blog_publicacion_directa(self) -> None:
        service = AmigosService(_MemoryStore())
        service.grant_authorization(
            actor_user_id=_ADMIN, is_global_admin=True, user_id="author", scope="blog",
            direct_publish=True,
        )
        article = service.create_general_article(
            actor_user_id="author", is_global_admin=False, title="Directo",
            event_date="2026-03-01", body="y", action="publish",
        )
        assert article["status"] == "published"

    def test_blog_publicar_articulo_general_por_autor(self) -> None:
        """El autor publica su propio artículo del blog (sin grupo) y no recibe 403."""
        service = AmigosService(_MemoryStore())
        service.grant_authorization(
            actor_user_id=_ADMIN, is_global_admin=True, user_id="author", scope="blog",
            direct_publish=True,
        )
        article = service.create_general_article(
            actor_user_id="author", is_global_admin=False, title="Borrador",
            event_date="2026-03-01", body="y", action="draft",
        )
        published = service.publish_article(
            actor_user_id="author", is_global_admin=False, article_id=str(article["id"])
        )
        assert published["status"] == "published"

    def test_blog_publicar_sin_directo_queda_pendiente(self) -> None:
        service = AmigosService(_MemoryStore())
        service.grant_authorization(
            actor_user_id=_ADMIN, is_global_admin=True, user_id="author", scope="blog"
        )
        article = service.create_general_article(
            actor_user_id="author", is_global_admin=False, title="Borrador",
            event_date="2026-03-01", body="y", action="draft",
        )
        result = service.publish_article(
            actor_user_id="author", is_global_admin=False, article_id=str(article["id"])
        )
        assert result["status"] == "pending"
        assert service.get_public_general_article(str(article["id"])) is None

    def test_blog_ajeno_no_publica(self) -> None:
        service = AmigosService(_MemoryStore())
        service.grant_authorization(
            actor_user_id=_ADMIN, is_global_admin=True, user_id="author", scope="blog"
        )
        article = service.create_general_article(
            actor_user_id="author", is_global_admin=False, title="X",
            event_date="2026-03-01", body="y", action="draft",
        )
        with pytest.raises(AmigosError) as exc:
            service.publish_article(
                actor_user_id="stranger", is_global_admin=False, article_id=str(article["id"])
            )
        assert exc.value.status == 403

    def test_articulo_general_expone_group_id_vacio(self) -> None:
        """El blog (sin grupo) no debe exponer `group_id = "None"` al frontend."""
        from src.osap.api.platform.amigos import AmigosMixin

        store = _MemoryStore()
        article = AmigosService(store).create_general_article(
            actor_user_id=_ADMIN, is_global_admin=True, title="Nota",
            event_date="2026-03-01", body="y", action="publish",
        )

        class _Api(AmigosMixin):
            def __init__(self, op_store: object) -> None:
                self._store = op_store  # type: ignore[assignment]

        row = store.get_amigos_article(str(article["id"]))
        assert row is not None
        read = _Api(store)._amigos_article_read(row)
        assert read.group_id == ""
        assert read.group_name is None

    def test_eventos_autor_autorizado_queda_pendiente(self) -> None:
        service = AmigosService(_MemoryStore())
        with pytest.raises(AmigosError):
            service.create_actuacion(
                actor_user_id="u1", is_global_admin=False,
                data={"title": "E", "starts_on": "2099-05-01"}, action="publish",
            )
        service.grant_authorization(
            actor_user_id=_ADMIN, is_global_admin=True, user_id="u1", scope="events"
        )
        event = service.create_actuacion(
            actor_user_id="u1", is_global_admin=False,
            data={"title": "E", "starts_on": "2099-05-01"}, action="publish",
        )
        assert event["editorial_status"] == "pending"


class TestRichtext:
    def test_sanitiza_html_del_cuerpo(self) -> None:
        from src.osap.domain.richtext import looks_like_html, sanitize_body

        assert not looks_like_html("Hola\n\nmundo")
        assert sanitize_body("Hola\n\nmundo") == "Hola\n\nmundo"
        html = (
            '<div class="articulo-osap"><p>Hola <strong>mundo</strong></p></div>'
            '<script>alert(1)</script>'
            '<style>body{color:red}@import url("http://x/y.css");a{background:url(http://e/p.png)}</style>'
            '<a href="javascript:alert(1)">x</a><a href="/rel">r</a><p onclick="x()">a</p>'
        )
        out = sanitize_body(html)
        assert '<div class="articulo-osap">' in out
        assert "<p>" in out and "<strong>mundo</strong>" in out
        assert "script" not in out and "javascript:" not in out
        assert 'href="/rel"' in out
        # <style> se conserva; se filtran @import y url(...)
        assert "<style>" in out and "color:red" in out
        assert "@import" not in out and "url(" not in out
        # atributos peligrosos fuera
        assert "onclick" not in out

    def test_texto_suelto_en_cuerpo_html_se_envuelve_en_parrafos(self) -> None:
        """Un cuerpo con HTML (p. ej. `<style>` + `<div>`) conserva los retornos como `<p>`."""
        from src.osap.domain.richtext import sanitize_body

        html = (
            "<style>.articulo-osap p{font-size:20px}</style>"
            '<div class="articulo-osap">Hola mundo\n\nSegundo parrafo\ncon salto</div>'
        )
        out = sanitize_body(html)
        assert "<p>Hola mundo</p>" in out
        assert "<p>Segundo parrafo<br>con salto</p>" in out
        assert "font-size:20px" in out

    def test_parrafos_existentes_no_se_duplican(self) -> None:
        from src.osap.domain.richtext import sanitize_html

        assert sanitize_html("<p>a</p>\n<p>b</p>") == "<p>a</p><p>b</p>"
        assert sanitize_html("<p>a <strong>b</strong> c</p>") == "<p>a <strong>b</strong> c</p>"
        assert sanitize_html("<ul>\n<li>uno</li>\n<li>dos</li>\n</ul>") == (
            "<ul><li>uno</li><li>dos</li></ul>"
        )

    def test_plain_text_quita_estilos_y_etiquetas(self) -> None:
        from src.osap.domain.richtext import plain_text

        assert plain_text("<style>.a{color:red}</style><p>Hola</p>\n<p>Mundo</p>") == "Hola Mundo"
        assert plain_text("Texto plano\n\nen dos lineas") == "Texto plano en dos lineas"

    def test_enlaces_en_texto_plano(self) -> None:
        """Un cuerpo de texto plano puede llevar enlaces: URL suelta o `[texto](url)`."""
        from src.osap.domain.richtext import to_html_body

        out = to_html_body("Mira https://osap.example y [Guía](https://x.org)")
        assert (
            '<a href="https://osap.example" rel="nofollow noopener">https://osap.example</a>' in out
        )
        assert '<a href="https://x.org" rel="nofollow noopener">Guía</a>' in out

    def test_enlaces_peligrosos_no_se_enlazan(self) -> None:
        from src.osap.domain.richtext import to_html_body

        out = to_html_body("[malo](javascript:alert(1))")
        assert "<a" not in out
        assert "javascript:alert(1)" in out

    def test_to_html_body_sanea_el_html(self) -> None:
        from src.osap.domain.richtext import to_html_body

        out = to_html_body("<p>Hola</p><script>x</script>")
        assert "<p>Hola</p>" in out
        assert "script" not in out


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

    def test_upload_requiere_login_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi
        from src.osap.domain.votes import UnauthenticatedError

        def fake(self: Any, *a: Any, **kw: Any) -> Any:
            raise UnauthenticatedError("login required")

        monkeypatch.setattr(PlatformApi, "amigos_upload", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.post(
                "/api/v1/amigos/uploads?group_id=g&name=x.png&mime_type=image/png",
                content=b"123",
            )
        assert resp.status_code == 401

    def test_media_desconocida_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.osap.api import platform_app
        from src.osap.api.platform import PlatformApi

        def fake(self: Any, file_id: int) -> Any:
            return None

        monkeypatch.setattr(PlatformApi, "amigos_media", fake)
        with TestClient(platform_app.create_platform_app()) as client:
            resp = client.get("/api/v1/amigos/media/999999")
        assert resp.status_code == 404

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
        # Fecha en formato europeo (dd/mm/aaaa).
        assert "20/12/2026" in page.text
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
