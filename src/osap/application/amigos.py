"""Circuito de «Los amigos»: grupos, membresías, artículos y recursos audiovisuales.

Capa de aplicación pura: recibe el `actor_user_id` ya resuelto por el API y un indicador
`is_global_admin`, y **aplica la autorización real** consultando las membresías del grupo
en el almacén. El frontend nunca decide permisos.

Reglas clave (ver `docs/osap/amigos.md`):
- Solo un miembro ACTIVO del grupo (o un admin global) puede contribuir.
- Modalidad editorial `direct`: el colaborador publica; `moderated`: su artículo queda
  `pending` hasta que un admin del grupo lo aprueba.
- El autor original (`author_user_id`) es inmutable: editar no lo cambia.
- Revocar la membresía impide nuevas contribuciones pero NO borra artículos publicados.
- Retirar (`withdrawn`) oculta sin borrar (trazabilidad).
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import UTC, date, datetime
from typing import Any

from src.osap.domain.amigos import (
    EDITORIAL_MODES,
    FORMATION_TYPES,
    GROUP_KINDS,
    GROUP_LINK_KINDS,
    GROUP_STATUSES,
    MEDIA_KINDS,
    MEMBER_ROLES,
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_DASHES = re.compile(r"[\u2010-\u2015\u2212]")
_YOUTUBE_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be")
_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
_URL_SCHEME = re.compile(r"^https?://", re.IGNORECASE)

# Campos escalares de la ficha de coral (especialización por tipo).
_CORAL_FIELDS = (
    "foundation_date", "dissolution_date", "locality", "region", "country_code",
    "venue", "formation_type", "member_count", "website", "public_email",
    "director_person_id", "director_label", "linked_entity",
)


def _slugify(text: str, *, max_len: int = 80) -> str:
    prepped = _DASHES.sub(" ", text or "")
    normalized = unicodedata.normalize("NFKD", prepped)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_ALNUM.sub("-", ascii_text).strip("-")
    return slug[:max_len].strip("-")


def _now() -> str:
    # Formato compatible con DATETIME de MySQL/MariaDB: sin 'T' ni offset de zona
    # (un ISO con 'T'/'+00:00' provoca error 1292 en la columna published_at).
    return datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")


def youtube_id(url: str) -> str | None:
    """Extrae el id del vídeo de una URL de YouTube, o `None` si no es válida.

    Solo acepta hosts de YouTube y esquema http(s): nunca se acepta HTML/JS.
    """
    if not _URL_SCHEME.match(url or ""):
        return None
    rest = url.split("://", 1)[1]
    host_and_path = rest.split("?", 1)
    host = host_and_path[0].split("/", 1)[0].lower()
    if host not in _YOUTUBE_HOSTS:
        return None
    query = host_and_path[1] if len(host_and_path) > 1 else ""
    if host.endswith("youtu.be"):
        candidate = host_and_path[0].split("/", 1)[1] if "/" in host_and_path[0] else ""
    elif "v=" in query:
        candidate = query.split("v=", 1)[1].split("&", 1)[0]
    else:
        parts = host_and_path[0].split("/")
        # /embed/<id> | /shorts/<id> | /live/<id>
        candidate = parts[2] if len(parts) > 2 and parts[1] in ("embed", "shorts", "live") else ""
    candidate = candidate.strip("/").split("/", 1)[0]
    return candidate if _YOUTUBE_ID.match(candidate) else None


class AmigosError(Exception):
    """Error controlado del circuito de «Los amigos» (código HTTP + mensaje seguro)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class AmigosService:
    def __init__(self, store: Any) -> None:
        self._store = store

    # --- grupos (lectura pública) -------------------------------------------

    def list_groups(
        self, *, active_only: bool = True, kind: str | None = None
    ) -> list[dict[str, object]]:
        if kind is not None and kind not in GROUP_KINDS:
            raise AmigosError(422, "INVALID_KIND", "Tipo de grupo no soportado")
        return list(self._store.list_amigos_groups(active_only=active_only, kind=kind))

    def get_group(self, group_id: str) -> dict[str, object] | None:
        row = self._store.get_amigos_group(group_id)
        return dict(row) if row is not None else None

    # --- grupos (administración global) -------------------------------------

    def create_group(
        self,
        *,
        actor_user_id: str,
        is_global_admin: bool,
        name: str,
        kind: str = "coral",
        slug: str | None = None,
        description: str | None = None,
        image_url: str | None = None,
        editorial_mode: str = "moderated",
        website: str | None = None,
        email: str | None = None,
        logo_url: str | None = None,
        links: list[dict[str, Any]] | None = None,
    ) -> dict[str, object]:
        if not is_global_admin:
            raise AmigosError(403, "FORBIDDEN", "Solo la administración global crea grupos")
        clean_name = (name or "").strip()
        if not clean_name:
            raise AmigosError(422, "NAME_REQUIRED", "El nombre del grupo es obligatorio")
        if kind not in GROUP_KINDS:
            raise AmigosError(422, "INVALID_KIND", "Tipo de grupo no soportado")
        if editorial_mode not in EDITORIAL_MODES:
            raise AmigosError(422, "INVALID_EDITORIAL_MODE", "Modalidad editorial inválida")
        clean_slug = _slugify(slug or clean_name, max_len=96) or "grupo"
        if self._store.get_amigos_group_by_slug(clean_slug) is not None:
            raise AmigosError(409, "SLUG_TAKEN", "Ese slug de grupo ya existe")
        row = dict(
            self._store.add_amigos_group(
                group_id=secrets.token_hex(8),
                slug=clean_slug,
                name=clean_name,
                kind=kind,
                description=description,
                image_url=_clean_url(image_url),
                editorial_mode=editorial_mode,
                created_by=actor_user_id,
                website=_clean_url(website),
                email=_validate_email(email),
                logo_url=_clean_url(logo_url),
            )
        )
        self._store.replace_amigos_group_links(str(row["id"]), _clean_links(links))
        return row

    def update_group(
        self,
        *,
        actor_user_id: str,
        is_global_admin: bool,
        group_id: str,
        name: str | None = None,
        description: str | None = None,
        image_url: str | None = None,
        editorial_mode: str | None = None,
        status: str | None = None,
        website: str | None = None,
        email: str | None = None,
        logo_url: str | None = None,
        links: list[dict[str, Any]] | None = None,
    ) -> dict[str, object]:
        self._require_group_admin(group_id, actor_user_id, is_global_admin)
        changes: dict[str, object] = {}
        if name is not None:
            clean = name.strip()
            if not clean:
                raise AmigosError(422, "NAME_REQUIRED", "El nombre no puede quedar vacío")
            changes["name"] = clean
        if description is not None:
            changes["description"] = description
        if image_url is not None:
            changes["image_url"] = _clean_url(image_url)
        if website is not None:
            changes["website"] = _clean_url(website)
        if email is not None:
            changes["email"] = _validate_email(email)
        if logo_url is not None:
            changes["logo_url"] = _clean_url(logo_url)
        if editorial_mode is not None:
            if editorial_mode not in EDITORIAL_MODES:
                raise AmigosError(422, "INVALID_EDITORIAL_MODE", "Modalidad editorial inválida")
            changes["editorial_mode"] = editorial_mode
        if status is not None:
            if status not in GROUP_STATUSES:
                raise AmigosError(422, "INVALID_STATUS", "Estado de grupo inválido")
            # Activar/desactivar un grupo es decisión de la administración global.
            if not is_global_admin:
                raise AmigosError(403, "FORBIDDEN", "Solo la administración global cambia el estado")
            changes["status"] = status
        row = self._store.update_amigos_group(group_id, **changes)
        if row is None:
            raise AmigosError(404, "GROUP_NOT_FOUND", "Grupo no encontrado")
        if links is not None:
            self._store.replace_amigos_group_links(group_id, _clean_links(links))
        if "editorial_mode" in changes:
            self._store.add_amigos_event(
                group_id=group_id,
                article_id=None,
                event_type="editorial_mode_changed",
                actor=actor_user_id,
                detail_json=_detail_change("editorial_mode", changes["editorial_mode"]),
            )
        return dict(row)

    # --- membresías ----------------------------------------------------------

    def grant_member(
        self,
        *,
        actor_user_id: str,
        is_global_admin: bool,
        group_id: str,
        user_id: str,
        role: str = "collaborator",
    ) -> dict[str, object]:
        target = (user_id or "").strip()
        if not target:
            raise AmigosError(422, "USER_REQUIRED", "Falta el usuario")
        if role not in MEMBER_ROLES:
            raise AmigosError(422, "INVALID_ROLE", "Rol de grupo inválido")
        # Designar/retirar ADMINISTRADORES de grupo queda reservado a la administración global.
        if role == "admin" and not is_global_admin:
            raise AmigosError(403, "FORBIDDEN", "Solo la administración global designa administradores")
        self._require_group_admin(group_id, actor_user_id, is_global_admin)
        if self._store.get_amigos_group(group_id) is None:
            raise AmigosError(404, "GROUP_NOT_FOUND", "Grupo no encontrado")
        row = self._store.set_amigos_member(
            group_id=group_id, user_id=target, role=role, status="active", granted_by=actor_user_id
        )
        self._store.add_amigos_event(
            group_id=group_id,
            article_id=None,
            event_type="member_granted",
            actor=actor_user_id,
            detail_json=_json({"user_id": target, "role": role}),
        )
        return dict(row)

    def revoke_member(
        self,
        *,
        actor_user_id: str,
        is_global_admin: bool,
        group_id: str,
        user_id: str,
    ) -> dict[str, object]:
        self._require_group_admin(group_id, actor_user_id, is_global_admin)
        current = self._store.get_amigos_member(group_id, user_id)
        if current is None:
            raise AmigosError(404, "MEMBER_NOT_FOUND", "El usuario no pertenece al grupo")
        # Un admin de grupo no puede revocar a otro admin: solo la administración global.
        if str(current.get("role")) == "admin" and not is_global_admin:
            raise AmigosError(403, "FORBIDDEN", "Solo la administración global retira administradores")
        row = self._store.set_amigos_member(
            group_id=group_id,
            user_id=user_id,
            role=str(current.get("role") or "collaborator"),
            status="revoked",
            granted_by=actor_user_id,
        )
        # Revocar NO elimina artículos publicados (trazabilidad).
        self._store.add_amigos_event(
            group_id=group_id,
            article_id=None,
            event_type="member_revoked",
            actor=actor_user_id,
            detail_json=_json({"user_id": user_id}),
        )
        return dict(row) if row is not None else {"group_id": group_id, "user_id": user_id, "status": "revoked"}

    def list_members(
        self, *, actor_user_id: str, is_global_admin: bool, group_id: str
    ) -> list[dict[str, object]]:
        self._require_group_admin(group_id, actor_user_id, is_global_admin)
        return list(self._store.list_amigos_members(group_id))

    # --- especialización por tipo: ficha de coral ---------------------------

    def get_coral_details(self, group_id: str) -> dict[str, object] | None:
        """Ficha estructurada de un coral, o `None` si el grupo no existe o no es de tipo coral."""
        group = self._store.get_amigos_group(group_id)
        if group is None or str(group.get("kind")) != "coral":
            return None
        return self._coral_read(group_id)

    def update_coral_details(
        self,
        *,
        actor_user_id: str,
        is_global_admin: bool,
        group_id: str,
        foundation_date: str | None = None,
        dissolution_date: str | None = None,
        locality: str | None = None,
        region: str | None = None,
        country_code: str | None = None,
        venue: str | None = None,
        formation_type: str | None = None,
        member_count: int | None = None,
        website: str | None = None,
        public_email: str | None = None,
        director_person_id: str | None = None,
        director_label: str | None = None,
        linked_entity: str | None = None,
        repertoire: list[str] | None = None,
        languages: list[str] | None = None,
        places: list[str] | None = None,
    ) -> dict[str, object]:
        group = self._store.get_amigos_group(group_id)
        if group is None:
            raise AmigosError(404, "GROUP_NOT_FOUND", "Grupo no encontrado")
        self._require_group_admin(group_id, actor_user_id, is_global_admin)
        if str(group.get("kind")) != "coral":
            raise AmigosError(422, "NOT_A_CORAL", "El grupo no es del tipo coral")
        fields: dict[str, object] = {
            "foundation_date": _validate_optional_date(foundation_date),
            "dissolution_date": _validate_optional_date(dissolution_date),
            "locality": _clean_text(locality),
            "region": _clean_text(region),
            "country_code": _validate_country_code(country_code),
            "venue": _clean_text(venue),
            "formation_type": _validate_formation_type(formation_type),
            "member_count": _validate_member_count(member_count),
            "website": _clean_url(website),
            "public_email": _validate_email(public_email),
            "director_person_id": _clean_text(director_person_id),
            "director_label": _clean_text(director_label),
            "linked_entity": _clean_text(linked_entity),
        }
        self._store.upsert_amigos_coral_details(group_id, **fields)
        if repertoire is not None or languages is not None or places is not None:
            existing = self._store.list_amigos_coral_attributes(group_id)
            items: list[dict[str, object]] = []
            pos = 0
            for facet, values in (
                ("repertoire", repertoire),
                ("language", languages),
                ("place", places),
            ):
                if values is not None:
                    chosen = _clean_multivalue(values)
                else:
                    chosen = [str(a["value"]) for a in existing if a.get("facet") == facet]
                for value in chosen:
                    items.append({"facet": facet, "value": value, "position": pos})
                    pos += 1
            self._store.replace_amigos_coral_attributes(group_id, items)
        self._store.add_amigos_event(
            group_id=group_id,
            article_id=None,
            event_type="coral_details_updated",
            actor=actor_user_id,
        )
        return self._coral_read(group_id) or {}

    def _coral_read(self, group_id: str) -> dict[str, object]:
        details = self._store.get_amigos_coral_details(group_id)
        data: dict[str, object] = {"group_id": group_id}
        for key in _CORAL_FIELDS:
            data[key] = None
        if details:
            data.update(details)
        attrs = self._store.list_amigos_coral_attributes(group_id)
        data["repertoire"] = [str(a["value"]) for a in attrs if a.get("facet") == "repertoire"]
        data["languages"] = [str(a["value"]) for a in attrs if a.get("facet") == "language"]
        data["places"] = [str(a["value"]) for a in attrs if a.get("facet") == "place"]
        return data

    # --- artículos: alta y edición ------------------------------------------

    def create_article(
        self,
        *,
        actor_user_id: str,
        is_global_admin: bool,
        group_id: str,
        title: str,
        event_date: str,
        body: str,
        summary: str | None = None,
        cover_url: str | None = None,
        media: list[dict[str, Any]] | None = None,
        action: str = "draft",
    ) -> dict[str, object]:
        role = self._require_can_contribute(group_id, actor_user_id, is_global_admin)
        clean_title = (title or "").strip()
        if not clean_title:
            raise AmigosError(422, "TITLE_REQUIRED", "El título es obligatorio")
        clean_date = _validate_event_date(event_date)
        if not (body or "").strip():
            raise AmigosError(422, "BODY_REQUIRED", "El texto del artículo es obligatorio")
        if action not in ("draft", "publish"):
            raise AmigosError(422, "INVALID_ACTION", "Acción inválida")
        group = self._store.get_amigos_group(group_id)
        assert group is not None
        status = self._initial_status(group, role, action)
        slug = self._unique_article_slug(group_id, clean_title)
        article = dict(
            self._store.create_amigos_article(
                article_id=secrets.token_hex(8),
                group_id=group_id,
                title=clean_title,
                slug=slug,
                event_date=clean_date,
                summary=(summary or "").strip() or None,
                body=body,
                cover_url=_clean_url(cover_url),
                author_user_id=actor_user_id,
                status=status,
            )
        )
        self._store.replace_amigos_media(article["id"], _clean_media(media or []))
        self._record_article_event(
            article, "article_created", actor_user_id, to_status=status
        )
        if status == "published":
            self._store.set_amigos_article_status(
                article_id=str(article["id"]),
                status="published",
                reviewed_by=actor_user_id,
                review_note=None,
                published_at=_now(),
            )
        return self.get_article_admin(str(article["id"]), actor_user_id, is_global_admin)  # type: ignore[return-value]

    def update_article(
        self,
        *,
        actor_user_id: str,
        is_global_admin: bool,
        article_id: str,
        title: str | None = None,
        event_date: str | None = None,
        body: str | None = None,
        summary: str | None = None,
        cover_url: str | None = None,
        media: list[dict[str, Any]] | None = None,
    ) -> dict[str, object]:
        article = self._require_article(article_id)
        group_id = str(article["group_id"])
        is_author = str(article["author_user_id"]) == actor_user_id
        is_group_admin = self._is_group_admin(group_id, actor_user_id)
        if not (is_author or is_group_admin or is_global_admin):
            raise AmigosError(403, "FORBIDDEN", "No puedes editar este artículo")
        # El autor solo edita sus propios borradores/pendientes; el admin puede corregir
        # cualquier estado (incluido publicado) sin cambiar la autoría.
        if (
            is_author
            and not (is_group_admin or is_global_admin)
            and str(article["status"]) not in ("draft", "pending")
        ):
            raise AmigosError(409, "NOT_EDITABLE", "Solo puedes editar borradores o pendientes")
        changes: dict[str, object] = {}
        if title is not None:
            clean = title.strip()
            if not clean:
                raise AmigosError(422, "TITLE_REQUIRED", "El título no puede quedar vacío")
            changes["title"] = clean
        if event_date is not None:
            changes["event_date"] = _validate_event_date(event_date)
        if body is not None:
            if not body.strip():
                raise AmigosError(422, "BODY_REQUIRED", "El texto no puede quedar vacío")
            changes["body"] = body
        if summary is not None:
            changes["summary"] = summary.strip() or None
        if cover_url is not None:
            changes["cover_url"] = _clean_url(cover_url)
        if changes:
            self._store.update_amigos_article(article_id, **changes)
        if media is not None:
            self._store.replace_amigos_media(article_id, _clean_media(media))
        self._store.add_amigos_event(
            group_id=group_id,
            article_id=article_id,
            event_type="article_edited",
            actor=actor_user_id,
            detail_json=_json({"fields": sorted(changes.keys())}),
        )
        return self.get_article_admin(article_id, actor_user_id, is_global_admin)  # type: ignore[return-value]

    def submit_article(
        self, *, actor_user_id: str, is_global_admin: bool, article_id: str
    ) -> dict[str, object]:
        article = self._require_article(article_id)
        self._require_author_or_admin(article, actor_user_id, is_global_admin)
        if str(article["status"]) != "draft":
            raise AmigosError(409, "INVALID_TRANSITION", "Solo un borrador se puede enviar")
        group = self._store.get_amigos_group(str(article["group_id"]))
        mode = str(group.get("editorial_mode")) if group else "moderated"
        target = "published" if mode == "direct" else "pending"
        return self._transition(article, target, actor_user_id, is_global_admin, event="article_submitted")

    def publish_article(
        self, *, actor_user_id: str, is_global_admin: bool, article_id: str
    ) -> dict[str, object]:
        article = self._require_article(article_id)
        group_id = str(article["group_id"])
        role = self._require_can_contribute(group_id, actor_user_id, is_global_admin)
        current = str(article["status"])
        if current == "published":
            return self.get_article_admin(article_id, actor_user_id, is_global_admin)  # type: ignore[return-value]
        if current not in ("draft", "pending"):
            raise AmigosError(409, "INVALID_TRANSITION", "El artículo no se puede publicar ahora")
        # Un colaborador (no admin del grupo) solo publica directo si la modalidad es `direct`.
        if role == "collaborator":
            group = self._store.get_amigos_group(group_id)
            if group is None or str(group.get("editorial_mode")) != "direct":
                raise AmigosError(
                    409, "APPROVAL_REQUIRED", "Este grupo requiere aprobación previa del administrador"
                )
        return self._transition(article, "published", actor_user_id, is_global_admin, event="article_published")

    def approve_article(
        self, *, actor_user_id: str, is_global_admin: bool, article_id: str
    ) -> dict[str, object]:
        article = self._require_article(article_id)
        self._require_group_admin(str(article["group_id"]), actor_user_id, is_global_admin)
        if str(article["status"]) != "pending":
            raise AmigosError(409, "INVALID_TRANSITION", "El artículo no está pendiente")
        return self._transition(article, "published", actor_user_id, is_global_admin, event="article_approved")

    def return_article(
        self, *, actor_user_id: str, is_global_admin: bool, article_id: str, note: str | None = None
    ) -> dict[str, object]:
        article = self._require_article(article_id)
        self._require_group_admin(str(article["group_id"]), actor_user_id, is_global_admin)
        if str(article["status"]) != "pending":
            raise AmigosError(409, "INVALID_TRANSITION", "El artículo no está pendiente")
        row = self._store.set_amigos_article_status(
            article_id=article_id,
            status="draft",
            reviewed_by=actor_user_id,
            review_note=(note or "").strip() or None,
            published_at=None,
        )
        self._record_article_event(article, "article_returned", actor_user_id, to_status="draft")
        assert row is not None
        return self.get_article_admin(article_id, actor_user_id, is_global_admin)  # type: ignore[return-value]

    def withdraw_article(
        self, *, actor_user_id: str, is_global_admin: bool, article_id: str
    ) -> dict[str, object]:
        article = self._require_article(article_id)
        self._require_author_or_admin(article, actor_user_id, is_global_admin)
        if str(article["status"]) == "withdrawn":
            return self.get_article_admin(article_id, actor_user_id, is_global_admin)  # type: ignore[return-value]
        row = self._store.set_amigos_article_status(
            article_id=article_id,
            status="withdrawn",
            reviewed_by=actor_user_id if not self._is_author(article, actor_user_id) else None,
            review_note=None,
            published_at=None,
        )
        self._record_article_event(article, "article_withdrawn", actor_user_id, to_status="withdrawn")
        assert row is not None
        return self.get_article_admin(article_id, actor_user_id, is_global_admin)  # type: ignore[return-value]

    # --- artículos: lectura --------------------------------------------------

    def list_group_articles(
        self,
        *,
        group_id: str,
        include_non_public: bool,
        actor_user_id: str | None,
        is_global_admin: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        statuses = None
        if not is_global_admin and (
            not include_non_public or not self._is_group_admin(group_id, actor_user_id or "")
        ):
            statuses = ["published"]
        rows, total = self._store.list_amigos_articles(
            group_id=group_id, statuses=statuses, limit=limit, offset=offset
        )
        return {"items": [self._article_read(r, include_media=False) for r in rows], "total": total}

    def list_my_articles(
        self, *, actor_user_id: str, limit: int = 100, offset: int = 0
    ) -> dict[str, object]:
        rows, total = self._store.list_amigos_articles_by_author(
            actor_user_id, limit=limit, offset=offset
        )
        return {"items": [self._article_read(r) for r in rows], "total": total}

    def list_pending(
        self,
        *,
        actor_user_id: str,
        is_global_admin: bool,
        group_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        if group_id is not None:
            self._require_group_admin(group_id, actor_user_id, is_global_admin)
            allowed = [group_id]
        elif is_global_admin:
            allowed = None
        else:
            allowed = [
                str(m["group_id"])
                for m in self._my_admin_groups(actor_user_id)
            ]
            if not allowed:
                return {"items": [], "total": 0}
        rows, total = self._store.list_amigos_articles(
            group_id=None, group_ids=allowed, statuses=["pending"], limit=limit, offset=offset
        )
        return {"items": [self._article_read(r) for r in rows], "total": total}

    def get_public_article(self, article_id: str) -> dict[str, object] | None:
        row = self._store.get_amigos_article(article_id)
        if row is None or str(row["status"]) != "published":
            return None
        return self._article_read(row, include_media=True)

    def get_article_for_reader(
        self, *, article_id: str, actor_user_id: str | None, is_global_admin: bool
    ) -> dict[str, object] | None:
        row = self._store.get_amigos_article(article_id)
        if row is None:
            return None
        if str(row["status"]) == "published" or is_global_admin:
            return self._article_read(row, include_media=True)
        if actor_user_id and (
            self._is_author(row, actor_user_id)
            or self._is_group_admin(str(row["group_id"]), actor_user_id)
        ):
            return self._article_read(row, include_media=True)
        return None

    def get_article_admin(
        self, article_id: str, actor_user_id: str, is_global_admin: bool
    ) -> dict[str, object] | None:
        row = self._store.get_amigos_article(article_id)
        if row is None:
            return None
        if not is_global_admin and not (
            self._is_author(row, actor_user_id)
            or self._is_group_admin(str(row["group_id"]), actor_user_id)
        ):
            return None
        return self._article_read(row, include_media=True)

    # --- auditoría -----------------------------------------------------------

    def list_events(self, *, group_id: str) -> list[dict[str, object]]:
        return list(self._store.list_amigos_events(group_id=group_id, article_id=None))

    # --- helpers de permisos -------------------------------------------------

    def _membership(self, group_id: str, user_id: str) -> dict[str, object] | None:
        row = self._store.get_amigos_member(group_id, user_id)
        if row is None or str(row.get("status")) != "active":
            return None
        return dict(row)

    def _is_group_admin(self, group_id: str, user_id: str) -> bool:
        row = self._membership(group_id, user_id)
        return row is not None and str(row.get("role")) == "admin"

    def _require_group_admin(self, group_id: str, actor_user_id: str, is_global_admin: bool) -> None:
        if is_global_admin:
            return
        if not self._is_group_admin(group_id, actor_user_id):
            raise AmigosError(403, "FORBIDDEN", "Se requiere ser administrador del grupo")

    def _require_can_contribute(
        self, group_id: str, actor_user_id: str, is_global_admin: bool
    ) -> str:
        """Devuelve el rol efectivo (`admin`/`collaborator`); 403 si no puede contribuir."""
        if is_global_admin:
            return "admin"
        role = self._membership(group_id, actor_user_id)
        if role is None:
            raise AmigosError(403, "FORBIDDEN", "No estás autorizado en este grupo")
        return str(role.get("role") or "collaborator")

    def _require_author_or_admin(
        self, article: dict[str, object], actor_user_id: str, is_global_admin: bool
    ) -> None:
        if is_global_admin or self._is_author(article, actor_user_id):
            return
        if self._is_group_admin(str(article["group_id"]), actor_user_id):
            return
        raise AmigosError(403, "FORBIDDEN", "No autorizado sobre este artículo")

    @staticmethod
    def _is_author(article: dict[str, object], actor_user_id: str) -> bool:
        return str(article.get("author_user_id")) == actor_user_id

    def _require_article(self, article_id: str) -> dict[str, object]:
        row = self._store.get_amigos_article(article_id)
        if row is None:
            raise AmigosError(404, "ARTICLE_NOT_FOUND", "Artículo no encontrado")
        return dict(row)

    def _my_admin_groups(self, actor_user_id: str) -> list[dict[str, object]]:
        return [
            m
            for m in self._store.list_amigos_memberships_by_user(actor_user_id)
            if str(m.get("role")) == "admin" and str(m.get("status")) == "active"
        ]

    # --- helpers de transición ----------------------------------------------

    def _initial_status(self, group: dict[str, object], role: str, action: str) -> str:
        if action == "draft":
            return "draft"
        if role == "admin":
            return "published"
        return "published" if str(group.get("editorial_mode")) == "direct" else "pending"

    def _transition(
        self,
        article: dict[str, object],
        target: str,
        actor_user_id: str,
        is_global_admin: bool,
        *,
        event: str,
    ) -> dict[str, object]:
        article_id = str(article["id"])
        published_at = _now() if target == "published" else None
        self._store.set_amigos_article_status(
            article_id=article_id,
            status=target,
            reviewed_by=actor_user_id,
            review_note=None,
            published_at=published_at,
        )
        self._record_article_event(article, event, actor_user_id, to_status=target)
        return self.get_article_admin(article_id, actor_user_id, is_global_admin)  # type: ignore[return-value]

    def _record_article_event(
        self,
        article: dict[str, object],
        event_type: str,
        actor: str,
        *,
        to_status: str | None = None,
    ) -> None:
        self._store.add_amigos_event(
            group_id=str(article["group_id"]),
            article_id=str(article["id"]),
            event_type=event_type,
            actor=actor,
            from_status=str(article.get("status")) if article.get("status") else None,
            to_status=to_status,
        )

    # --- serialización -------------------------------------------------------

    def _article_read(
        self, row: dict[str, object], *, include_media: bool = False
    ) -> dict[str, object]:
        data = dict(row)
        if include_media:
            data["media"] = list(self._store.list_amigos_media(str(row["id"])))
        return data

    def _unique_article_slug(self, group_id: str, title: str) -> str:
        base = _slugify(title, max_len=120) or "articulo"
        candidate = base
        suffix = 2
        while self._store.get_amigos_article_by_slug(group_id, candidate) is not None:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate


def _json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)


def _detail_change(field: str, value: object) -> str:
    return _json({"field": field, "value": value})


def _validate_event_date(value: str) -> str:
    text = (value or "").strip()
    try:
        # `fromisoformat` exige AAAA-MM-DD y rechaza fechas imposibles (p. ej. 2026-02-31),
        # que la columna DATE de MySQL rechazaría con un error no controlado.
        parsed = date.fromisoformat(text)
    except ValueError:
        raise AmigosError(
            422, "INVALID_EVENT_DATE", "La fecha del evento debe ser AAAA-MM-DD"
        ) from None
    if parsed.isoformat() != text:
        raise AmigosError(422, "INVALID_EVENT_DATE", "La fecha del evento debe ser AAAA-MM-DD")
    return text


def _clean_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _validate_optional_date(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        raise AmigosError(422, "INVALID_DATE", "Fecha inválida (formato AAAA-MM-DD)") from None
    if parsed.isoformat() != text:
        raise AmigosError(422, "INVALID_DATE", "Fecha inválida (formato AAAA-MM-DD)")
    return text


def _validate_country_code(value: object) -> str | None:
    text = str(value).strip().upper() if value is not None else ""
    if not text:
        return None
    if not re.fullmatch(r"[A-Z]{2}", text):
        raise AmigosError(422, "INVALID_COUNTRY", "Código de país ISO 3166-1 alfa-2 (p. ej. ES)")
    return text


def _validate_formation_type(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    if text not in FORMATION_TYPES:
        raise AmigosError(422, "INVALID_FORMATION_TYPE", "Tipo de formación no válido")
    return text


def _validate_member_count(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        count = int(str(value))
    except (TypeError, ValueError):
        raise AmigosError(422, "INVALID_MEMBER_COUNT", "Número de integrantes inválido") from None
    if count < 0:
        raise AmigosError(422, "INVALID_MEMBER_COUNT", "Número de integrantes inválido")
    return count


def _validate_email(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    if " " in text or "@" not in text or len(text) > 254 or "." not in text.split("@", 1)[1]:
        raise AmigosError(422, "INVALID_EMAIL", "Correo público inválido")
    return text


def _clean_multivalue(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        text = str(raw).strip()[:120]
        # Dedupe sin distinguir mayúsculas: el índice único (group_id, facet, value) es
        # case-insensitive en utf8mb4_unicode_ci y rechazaría «Barroco»/«barroco» como par.
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _clean_url(value: str | None) -> str | None:
    """Acepta solo http(s) o vacío; nunca `javascript:`/`data:`."""
    text = (value or "").strip()
    if not text:
        return None
    if not _URL_SCHEME.match(text):
        raise AmigosError(422, "INVALID_URL", "Solo se admiten enlaces http(s)")
    return text


def _clean_links(items: list[dict[str, Any]] | None) -> list[dict[str, object]]:
    """Normaliza los enlaces comunes del grupo (web/social) validando tipo y URL http(s)."""
    cleaned: list[dict[str, object]] = []
    for index, item in enumerate(items or []):
        kind = str(item.get("kind") or "").strip()
        if kind not in GROUP_LINK_KINDS:
            raise AmigosError(422, "INVALID_LINK_KIND", "Tipo de enlace no válido")
        url = _clean_url(str(item.get("url") or ""))
        if url is None:
            raise AmigosError(422, "LINK_URL_REQUIRED", "Falta la URL del enlace")
        label = (str(item.get("label") or "").strip() or None)
        cleaned.append(
            {"kind": kind, "label": label[:64] if label else None, "url": url, "position": index}
        )
    return cleaned


def _clean_media(items: list[dict[str, Any]]) -> list[dict[str, object]]:
    """Normaliza vídeos (YouTube) y fotografías (enlace externo validado).

    Los vídeos se almacenan como URL + id + proveedor para incrustarlos de forma segura
    (nunca HTML/scripts del usuario).
    """
    cleaned: list[dict[str, object]] = []
    for index, item in enumerate(items):
        kind = str(item.get("kind") or "")
        if kind not in MEDIA_KINDS:
            raise AmigosError(422, "INVALID_MEDIA_KIND", "Tipo de recurso inválido")
        url = _clean_url(str(item.get("url") or ""))
        if url is None:
            raise AmigosError(422, "MEDIA_URL_REQUIRED", "Falta la URL del recurso")
        provider = None
        video_id = None
        if kind == "video":
            video_id = youtube_id(url)
            if video_id is None:
                raise AmigosError(422, "INVALID_VIDEO_URL", "Solo se admiten vídeos de YouTube")
            provider = "youtube"
        cleaned.append(
            {
                "kind": kind,
                "url": url,
                "provider": provider,
                "video_id": video_id,
                "caption": (str(item.get("caption") or "").strip() or None),
                "credit": (str(item.get("credit") or "").strip() or None),
                "position": int(item.get("position") or index),
            }
        )
    return cleaned
