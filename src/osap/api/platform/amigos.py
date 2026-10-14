"""PlatformApi: mixin de «Los amigos» (grupos, membresías, artículos, moderación).

Traduce HTTP (token → identidad) a llamadas del `AmigosService`, que aplica la
autorización real contra las membresías del grupo. El `actor_user_id` procede siempre de
la identidad autenticada; nunca del cuerpo. El rol global `admin` se comprueba aquí.
"""

from __future__ import annotations

import logging

from src.osap.api.contracts import (
    AmigosActuacionListRead,
    AmigosActuacionRead,
    AmigosActuacionRequest,
    AmigosArticleCreateRequest,
    AmigosArticleListRead,
    AmigosArticleRead,
    AmigosArticleUpdateRequest,
    AmigosAuthorizationListRead,
    AmigosAuthorizationRead,
    AmigosAuthorizationRequest,
    AmigosCoralDetailsRead,
    AmigosCoralDetailsUpdate,
    AmigosEventGroup,
    AmigosGroupCreateRequest,
    AmigosGroupLink,
    AmigosGroupRead,
    AmigosGroupUpdateRequest,
    AmigosMediaRead,
    AmigosMemberGrantRequest,
    AmigosMemberListRead,
    AmigosMemberRead,
)
from src.osap.api.platform.core import PlatformApiCore
from src.osap.api.seo.views import public_base_url
from src.osap.application.amigos import AmigosError, AmigosService
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError

_LOGGER = logging.getLogger("osap.amigos")

# Sentinela para distinguir "grupo no resuelto todavía" de "grupo resuelto y ausente (None)".
_GROUP_UNSET = object()


class AmigosMixin(PlatformApiCore):
    # --- helpers -------------------------------------------------------------

    def _amigos_service(self) -> AmigosService:
        return AmigosService(self._store)

    @staticmethod
    def _rows(data: dict[str, object]) -> list[dict[str, object]]:
        raw = data.get("items")
        return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []

    @staticmethod
    def _total(data: dict[str, object]) -> int:
        value = data.get("total")
        return int(str(value)) if value is not None else 0

    def _amigos_user(self, token: str | None) -> str:
        principal = self._container.authenticator().resolve(token)
        user_id = getattr(principal, "user_id", None) if principal is not None else None
        if not user_id:
            raise UnauthenticatedError("Login required")
        return str(user_id)

    def _amigos_actor_email(self, token: str | None) -> str | None:
        try:
            code, doc = self._container.auth_proxy().me(token or "")
        except Exception as exc:  # noqa: BLE001 — si auth no responde, no hay email
            _LOGGER.warning("amigos: email de autor sin osap-auth (%s)", exc)
            return None
        if code == 200 and isinstance(doc, dict):
            email = doc.get("email")
            return str(email) if email else None
        return None

    def _amigos_is_global_admin(self, token: str | None) -> bool:
        principal = self._container.authenticator().resolve(token)
        if principal is None:
            return False
        has_role = getattr(principal, "has_role", None)
        if callable(has_role) and has_role("admin"):
            return True
        # El claim `roles` es una foto del token; osap-auth (BD) es la autoridad.
        try:
            code, doc = self._container.auth_proxy().me(token or "")
        except Exception as exc:  # noqa: BLE001 — si auth no responde, no se concede admin
            _LOGGER.warning("amigos: comprobación admin sin osap-auth (%s)", exc)
            return False
        roles = doc.get("roles") if isinstance(doc, dict) else None
        return code == 200 and isinstance(roles, list) and "admin" in roles

    # --- lectura pública -----------------------------------------------------

    def amigos_list_groups(
        self, *, token: str | None = None, include_inactive: bool = False, kind: str | None = None
    ) -> list[AmigosGroupRead]:
        # Los grupos inactivos solo los ve la administración global.
        if include_inactive and not self._amigos_is_global_admin(token):
            raise ForbiddenError("Solo la administración global puede listar grupos inactivos")
        rows = self._amigos_service().list_groups(active_only=not include_inactive, kind=kind)
        return [self._amigos_group_read(row) for row in rows]

    def amigos_group_exists(self, group_id: str) -> bool:
        group = self._amigos_service().get_group(group_id)
        return group is not None and str(group.get("status")) == "active"

    def amigos_group_articles(
        self,
        group_id: str,
        *,
        token: str | None = None,
        include_non_public: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> AmigosArticleListRead:
        actor = None
        is_admin = False
        if token:
            try:
                actor = self._amigos_user(token)
                is_admin = self._amigos_is_global_admin(token)
            except UnauthenticatedError:
                actor, is_admin = None, False
        data = self._amigos_service().list_group_articles(
            group_id=group_id,
            include_non_public=include_non_public,
            actor_user_id=actor,
            is_global_admin=is_admin,
            limit=limit,
            offset=offset,
        )
        return AmigosArticleListRead(
            items=self._articles_read(self._rows(data)), total=self._total(data)
        )

    def amigos_article(self, article_id: str, *, token: str | None = None) -> AmigosArticleRead | None:
        actor = None
        is_admin = False
        if token:
            try:
                actor = self._amigos_user(token)
                is_admin = self._amigos_is_global_admin(token)
            except UnauthenticatedError:
                actor, is_admin = None, False
        row = self._amigos_service().get_article_for_reader(
            article_id=article_id, actor_user_id=actor, is_global_admin=is_admin
        )
        return self._amigos_article_read(row) if row else None

    def amigos_my_articles(
        self, token: str | None, limit: int = 100, offset: int = 0
    ) -> AmigosArticleListRead:
        actor = self._amigos_user(token)
        data = self._amigos_service().list_my_articles(
            actor_user_id=actor, limit=limit, offset=offset
        )
        items = self._articles_read(self._rows(data))
        return AmigosArticleListRead(items=items, total=self._total(data))

    def amigos_my_groups(self, token: str | None) -> list[dict[str, object]]:
        """Grupos en los que el usuario es miembro ACTIVO, con su rol (para el editor)."""
        actor = self._amigos_user(token)
        service = self._amigos_service()
        out: list[dict[str, object]] = []
        for membership in self._store.list_amigos_memberships_by_user(actor):
            if str(membership.get("status")) != "active":
                continue
            group = service.get_group(str(membership.get("group_id")))
            if group is None or str(group.get("status")) != "active":
                continue
            out.append(
                {
                    "group": self._amigos_group_read(group).model_dump(),
                    "role": str(membership.get("role") or "collaborator"),
                }
            )
        return out

    def amigos_pending(
        self, token: str | None, group_id: str | None, limit: int = 100, offset: int = 0
    ) -> AmigosArticleListRead:
        actor = self._amigos_user(token)
        is_admin = self._amigos_is_global_admin(token)
        data = self._amigos_service().list_pending(
            actor_user_id=actor, is_global_admin=is_admin, group_id=group_id,
            limit=limit, offset=offset,
        )
        items = self._articles_read(self._rows(data))
        return AmigosArticleListRead(items=items, total=self._total(data))

    # --- escritura: artículos ------------------------------------------------

    def amigos_create_article(
        self, token: str | None, group_id: str, payload: AmigosArticleCreateRequest
    ) -> AmigosArticleRead:
        actor = self._amigos_user(token)
        is_admin = self._amigos_is_global_admin(token)
        row = self._amigos_service().create_article(
            actor_user_id=actor,
            is_global_admin=is_admin,
            group_id=group_id,
            title=payload.title,
            event_date=payload.event_date,
            body=payload.body,
            summary=payload.summary,
            cover_url=payload.cover_url,
            media=[m.model_dump() for m in payload.media],
            action=payload.action,
        )
        return self._amigos_article_read(row)

    def amigos_update_article(
        self, token: str | None, article_id: str, payload: AmigosArticleUpdateRequest
    ) -> AmigosArticleRead | None:
        actor = self._amigos_user(token)
        is_admin = self._amigos_is_global_admin(token)
        media = [m.model_dump() for m in payload.media] if payload.media is not None else None
        row = self._amigos_service().update_article(
            actor_user_id=actor,
            is_global_admin=is_admin,
            article_id=article_id,
            title=payload.title,
            event_date=payload.event_date,
            body=payload.body,
            summary=payload.summary,
            cover_url=payload.cover_url,
            media=media,
        )
        return self._amigos_article_read(row) if row else None

    def amigos_submit_article(self, token: str | None, article_id: str) -> AmigosArticleRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().submit_article(
            actor_user_id=actor, is_global_admin=self._amigos_is_global_admin(token),
            article_id=article_id,
        )
        return self._amigos_article_read(row)

    def amigos_publish_article(self, token: str | None, article_id: str) -> AmigosArticleRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().publish_article(
            actor_user_id=actor, is_global_admin=self._amigos_is_global_admin(token),
            article_id=article_id,
        )
        return self._amigos_article_read(row)

    def amigos_withdraw_article(self, token: str | None, article_id: str) -> AmigosArticleRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().withdraw_article(
            actor_user_id=actor, is_global_admin=self._amigos_is_global_admin(token),
            article_id=article_id,
        )
        return self._amigos_article_read(row)

    # --- administración de grupos y moderación -------------------------------

    def amigos_create_group(
        self, token: str | None, payload: AmigosGroupCreateRequest
    ) -> AmigosGroupRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().create_group(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            name=payload.name,
            kind=payload.kind,
            slug=payload.slug,
            description=payload.description,
            image_url=payload.image_url,
            editorial_mode=payload.editorial_mode,
            website=payload.website,
            email=payload.email,
            logo_url=payload.logo_url,
            links=[link.model_dump() for link in payload.links],
        )
        return self._amigos_group_read(row)

    def amigos_update_group(
        self, token: str | None, group_id: str, payload: AmigosGroupUpdateRequest
    ) -> AmigosGroupRead | None:
        actor = self._amigos_user(token)
        row = self._amigos_service().update_group(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            group_id=group_id,
            name=payload.name,
            description=payload.description,
            image_url=payload.image_url,
            editorial_mode=payload.editorial_mode,
            status=payload.status,
            website=payload.website,
            email=payload.email,
            logo_url=payload.logo_url,
            links=[link.model_dump() for link in payload.links]
            if payload.links is not None
            else None,
        )
        return self._amigos_group_read(row)

    def amigos_grant_member(
        self, token: str | None, group_id: str, payload: AmigosMemberGrantRequest
    ) -> AmigosMemberRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().grant_member(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            group_id=group_id,
            user_id=payload.user_id,
            role=payload.role,
        )
        return self._amigos_member_read(row)

    def amigos_revoke_member(
        self, token: str | None, group_id: str, user_id: str
    ) -> AmigosMemberRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().revoke_member(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            group_id=group_id,
            user_id=user_id,
        )
        return self._amigos_member_read(row)

    # --- imágenes (osap-storage) --------------------------------------------

    def amigos_upload(
        self, token: str | None, group_id: str, name: str, mime_type: str | None, data: bytes
    ) -> dict[str, object]:
        actor = self._amigos_user(token)
        service = self._amigos_service()
        service.authorize_upload(
            group_id=group_id,
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
        )
        clean_name, mime = service.validate_upload(
            name=name, mime_type=mime_type, size_bytes=len(data)
        )
        try:
            uploaded = self._container.storage_contributions().upload_file(
                name=clean_name, mime_type=mime, data=data
            )
        except Exception as exc:  # noqa: BLE001 — storage caído
            raise AmigosError(502, "STORAGE_UNAVAILABLE", "Almacenamiento no disponible") from exc
        file_id = int(str(uploaded["id"]))
        service.record_upload(
            group_id=group_id,
            file_id=file_id,
            mime_type=mime,
            size_bytes=len(data),
            actor_user_id=actor,
        )
        return {"id": file_id, "url": f"{public_base_url()}/api/v1/amigos/media/{file_id}"}

    def amigos_media(self, file_id: int) -> tuple[str, bytes] | None:
        if self._amigos_service().get_upload(file_id) is None:
            return None
        try:
            return self._container.storage_contributions().fetch_file(file_id)
        except Exception as exc:  # noqa: BLE001 — storage caído
            raise AmigosError(502, "STORAGE_UNAVAILABLE", "Almacenamiento no disponible") from exc

    def amigos_list_members(self, token: str | None, group_id: str) -> AmigosMemberListRead:
        actor = self._amigos_user(token)
        rows = self._amigos_service().list_members(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            group_id=group_id,
        )
        return AmigosMemberListRead(items=[self._amigos_member_read(r) for r in rows], total=len(rows))

    # --- agenda: actuaciones y eventos --------------------------------------

    def amigos_list_events(
        self,
        token: str | None,
        *,
        public_only: bool,
        from_date: str | None = None,
        to_date: str | None = None,
        kind: str | None = None,
        locality: str | None = None,
        group_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AmigosActuacionListRead:
        is_admin = public_only is False and self._amigos_is_global_admin(token)
        data = self._amigos_service().list_actuaciones(
            public_only=not is_admin,
            from_date=from_date,
            to_date=to_date,
            kind=kind,
            locality=locality,
            group_id=group_id,
            limit=limit,
            offset=offset,
        )
        items = [self._amigos_event_read(r) for r in self._rows(data)]
        return AmigosActuacionListRead(items=items, total=self._total(data))

    def amigos_get_event(
        self, token: str | None, event_id: str, *, public_only: bool
    ) -> AmigosActuacionRead | None:
        if public_only and not self._amigos_is_global_admin(token):
            row = self._amigos_service().get_public_actuacion(event_id)
        else:
            row = self._amigos_service().get_actuacion(event_id)
        return self._amigos_event_read(row) if row is not None else None

    def amigos_create_event(
        self, token: str | None, payload: AmigosActuacionRequest
    ) -> AmigosActuacionRead:
        actor = self._amigos_user(token)
        is_admin = self._amigos_is_global_admin(token)
        data = payload.model_dump(exclude_unset=True)
        data["groups"] = [g.model_dump() for g in payload.groups]
        action = str(data.pop("action", "draft"))
        # Origen del anuncio: admin global → texto libre; si no, email de quien lo registra.
        if is_admin:
            data.pop("source_email", None)
        else:
            data.pop("source_note", None)
            email = self._amigos_actor_email(token)
            if email:
                data["source_email"] = email
        row = self._amigos_service().create_actuacion(
            actor_user_id=actor,
            is_global_admin=is_admin,
            data=data,
            action=action,
        )
        return self._amigos_event_read(row)

    def amigos_record_event_counter(
        self, event_id: str, kind: str
    ) -> dict[str, object] | None:
        count = self._amigos_service().record_event_counter(event_id, kind)
        if count is None:
            return None
        return {"id": event_id, "kind": kind, "count": count}

    def amigos_update_event(
        self, token: str | None, event_id: str, payload: AmigosActuacionRequest
    ) -> AmigosActuacionRead | None:
        actor = self._amigos_user(token)
        data = payload.model_dump(exclude_unset=True)
        if "groups" in data or payload.groups:
            data["groups"] = [g.model_dump() for g in payload.groups]
        data.pop("action", None)
        row = self._amigos_service().update_actuacion(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            actuacion_id=event_id,
            data=data,
        )
        return self._amigos_event_read(row)

    def amigos_set_event_status(
        self, token: str | None, event_id: str, editorial_status: str
    ) -> AmigosActuacionRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().set_actuacion_editorial(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            actuacion_id=event_id,
            editorial_status=editorial_status,
        )
        return self._amigos_event_read(row)

    def sitemap_amigos_events(self) -> list[dict[str, object]]:
        data = self._amigos_service().list_actuaciones(public_only=True, limit=10000, offset=0)
        out: list[dict[str, object]] = []
        for event in self._rows(data):
            out.append(
                {
                    "id": str(event.get("id") or ""),
                    "title": str(event.get("title") or ""),
                    "updated_at": str(event.get("updated_at") or ""),
                }
            )
        return out

    def seo_amigos_event(self, event_id: str) -> dict[str, object] | None:
        row = self._amigos_service().get_public_actuacion(event_id)
        return self._amigos_event_read(row).model_dump() if row is not None else None

    def _amigos_event_read(self, row: dict[str, object]) -> AmigosActuacionRead:
        def text(key: str) -> str | None:
            value = row.get(key)
            clean = str(value).strip() if value is not None else ""
            return clean or None

        lat = row.get("latitude")
        lon = row.get("longitude")
        raw_groups = row.get("groups")
        groups = [
            AmigosEventGroup(
                group_id=str(g.get("group_id") or ""),
                role=str(g.get("role") or "participant"),
            )
            for g in (raw_groups if isinstance(raw_groups, list) else [])
            if isinstance(g, dict)
        ]
        return AmigosActuacionRead(
            id=str(row["id"]),
            slug=str(row["slug"]),
            title=str(row.get("title") or ""),
            summary=text("summary"),
            description=text("description"),
            image_url=text("image_url"),
            kind=str(row.get("kind") or "other"),
            modality=str(row.get("modality") or "onsite"),
            event_status=str(row.get("event_status") or "scheduled"),
            editorial_status=str(row.get("editorial_status") or "draft"),
            starts_on=str(row.get("starts_on") or ""),
            starts_at=text("starts_at"),
            ends_on=text("ends_on"),
            ends_at=text("ends_at"),
            timezone=text("timezone"),
            registration_deadline=text("registration_deadline"),
            venue_name=text("venue_name"),
            venue_address=text("venue_address"),
            locality=text("locality"),
            region=text("region"),
            country_code=text("country_code"),
            latitude=float(str(lat)) if lat is not None else None,
            longitude=float(str(lon)) if lon is not None else None,
            map_url=text("map_url"),
            organizer_name=text("organizer_name"),
            organizer_website=text("organizer_website"),
            event_url=text("event_url"),
            tickets_url=text("tickets_url"),
            price=text("price"),
            access_info=text("access_info"),
            public_contact=text("public_contact"),
            organizer_group_id=text("organizer_group_id"),
            last_verified_on=text("last_verified_on"),
            author_user_id=str(row.get("author_user_id") or ""),
            published_at=text("published_at"),
            created_at=str(row.get("created_at") or ""),
            updated_at=str(row.get("updated_at") or ""),
            weight=int(str(row.get("weight") or 5)),
            views=int(str(row.get("views") or 0)),
            expands=int(str(row.get("expands") or 0)),
            buys=int(str(row.get("buys") or 0)),
            source_email=text("source_email"),
            source_note=text("source_note"),
            groups=groups,
        )

    # --- blog general «Artículos» -------------------------------------------

    def amigos_blog_articles(
        self, *, public_only: bool = True, limit: int = 100, offset: int = 0
    ) -> AmigosArticleListRead:
        data = self._amigos_service().list_blog_articles(
            public_only=public_only, limit=limit, offset=offset
        )
        items = [self._amigos_article_read(r) for r in self._rows(data)]
        return AmigosArticleListRead(items=items, total=self._total(data))

    def amigos_blog_article(
        self, article_id: str, *, token: str | None = None
    ) -> AmigosArticleRead | None:
        row = self._amigos_service().get_public_general_article(article_id)
        if row is not None:
            return self._amigos_article_read(row)
        if token:
            try:
                actor = self._amigos_user(token)
                is_admin = self._amigos_is_global_admin(token)
            except UnauthenticatedError:
                return None
            row = self._amigos_service().get_article_for_reader(
                article_id=article_id, actor_user_id=actor, is_global_admin=is_admin
            )
            return self._amigos_article_read(row) if row is not None else None
        return None

    def amigos_create_blog_article(
        self, token: str | None, payload: AmigosArticleCreateRequest
    ) -> AmigosArticleRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().create_general_article(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            title=payload.title,
            event_date=payload.event_date,
            body=payload.body,
            summary=payload.summary,
            cover_url=payload.cover_url,
            media=[m.model_dump() for m in payload.media],
            action=payload.action,
        )
        return self._amigos_article_read(row)

    def amigos_approve_blog_article(self, token: str | None, article_id: str) -> AmigosArticleRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().approve_general_article(
            actor_user_id=actor, is_global_admin=self._amigos_is_global_admin(token),
            article_id=article_id,
        )
        return self._amigos_article_read(row)

    def amigos_admin_blog_articles(
        self, token: str | None, limit: int = 200, offset: int = 0
    ) -> AmigosArticleListRead:
        if not self._amigos_is_global_admin(token):
            raise ForbiddenError("Se requiere administración global")
        data = self._amigos_service().list_blog_articles(
            public_only=False, limit=limit, offset=offset
        )
        items = [self._amigos_article_read(r) for r in self._rows(data)]
        return AmigosArticleListRead(items=items, total=self._total(data))

    # --- autorizaciones editoriales (blog/events) ---------------------------

    def amigos_grant_authorization(
        self, token: str | None, payload: AmigosAuthorizationRequest
    ) -> AmigosAuthorizationRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().grant_authorization(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            user_id=payload.user_id,
            scope=payload.scope,
            direct_publish=payload.direct_publish,
        )
        return self._amigos_authorization_read(row)

    def amigos_revoke_authorization(
        self, token: str | None, user_id: str, scope: str
    ) -> dict[str, object]:
        actor = self._amigos_user(token)
        self._amigos_service().revoke_authorization(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            user_id=user_id,
            scope=scope,
        )
        return {"user_id": user_id, "scope": scope, "revoked": True}

    def amigos_list_authorizations(
        self, token: str | None, scope: str
    ) -> AmigosAuthorizationListRead:
        actor = self._amigos_user(token)
        rows = self._amigos_service().list_authorizations(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            scope=scope,
        )
        return AmigosAuthorizationListRead(
            items=[self._amigos_authorization_read(r) for r in rows], total=len(rows)
        )

    def _amigos_authorization_read(self, row: dict[str, object]) -> AmigosAuthorizationRead:
        return AmigosAuthorizationRead(
            user_id=str(row.get("user_id") or ""),
            scope=str(row.get("scope") or ""),
            direct_publish=bool(row.get("direct_publish")),
            created_at=str(row.get("created_at") or ""),
        )

    # --- ficha de coral (especialización por tipo) ---------------------------

    def amigos_coral_details(self, group_id: str) -> AmigosCoralDetailsRead | None:
        row = self._amigos_service().get_coral_details(group_id)
        return self._amigos_coral_read(row) if row is not None else None

    def amigos_update_coral_details(
        self, token: str | None, group_id: str, payload: AmigosCoralDetailsUpdate
    ) -> AmigosCoralDetailsRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().update_coral_details(
            actor_user_id=actor,
            is_global_admin=self._amigos_is_global_admin(token),
            group_id=group_id,
            foundation_date=payload.foundation_date,
            dissolution_date=payload.dissolution_date,
            locality=payload.locality,
            region=payload.region,
            country_code=payload.country_code,
            venue=payload.venue,
            formation_type=payload.formation_type,
            member_count=payload.member_count,
            website=payload.website,
            public_email=payload.public_email,
            director_person_id=payload.director_person_id,
            director_label=payload.director_label,
            linked_entity=payload.linked_entity,
            repertoire=payload.repertoire,
            languages=payload.languages,
            places=payload.places,
        )
        return self._amigos_coral_read(row)

    def amigos_approve_article(self, token: str | None, article_id: str) -> AmigosArticleRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().approve_article(
            actor_user_id=actor, is_global_admin=self._amigos_is_global_admin(token),
            article_id=article_id,
        )
        return self._amigos_article_read(row)

    def amigos_return_article(
        self, token: str | None, article_id: str, note: str
    ) -> AmigosArticleRead:
        actor = self._amigos_user(token)
        row = self._amigos_service().return_article(
            actor_user_id=actor, is_global_admin=self._amigos_is_global_admin(token),
            article_id=article_id, note=note,
        )
        return self._amigos_article_read(row)

    def amigos_audit(self, token: str | None, group_id: str) -> list[dict[str, object]]:
        actor = self._amigos_user(token)
        self._amigos_service()  # valida existencia del servicio
        # Solo admin del grupo o admin global pueden ver el historial.
        is_admin_ok = self._amigos_is_global_admin(token) or self._amigos_service()._is_group_admin(
            group_id, actor
        )
        if not is_admin_ok:
            raise AmigosError(403, "FORBIDDEN", "Se requiere ser administrador del grupo")
        return self._amigos_service().list_events(group_id=group_id)

    # --- SEO (HTML server-rendered) -----------------------------------------

    def seo_amigos_group(self, group_id: str) -> dict[str, object] | None:
        group = self._amigos_service().get_group(group_id)
        if group is None or str(group.get("status")) != "active":
            return None
        data = self.amigos_group_articles(group_id, limit=500, offset=0)
        group["articles"] = [self._article_dict(a) for a in data.items]
        coral = self._amigos_service().get_coral_details(group_id)
        group["coral"] = self._amigos_coral_read(coral).model_dump() if coral is not None else None
        return group

    def seo_amigos_article(self, article_id: str) -> dict[str, object] | None:
        row = self._amigos_service().get_public_article(article_id)
        if row is None:
            return None
        # Se enriquece con `group_slug`/`group_name` para la URL canónica y el JSON-LD.
        return self._amigos_article_read(row).model_dump()

    # --- sitemap -------------------------------------------------------------

    def sitemap_amigos_groups(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for group in self._amigos_service().list_groups(active_only=True):
            out.append(
                {
                    "id": str(group["id"]),
                    "slug": str(group["slug"]),
                    "name": str(group["name"]),
                    "updated_at": str(group.get("updated_at") or ""),
                }
            )
        return out

    def sitemap_amigos_articles(self) -> list[dict[str, object]]:
        service = self._amigos_service()
        out: list[dict[str, object]] = []
        for group in service.list_groups(active_only=True):
            data = service.list_group_articles(
                group_id=str(group["id"]),
                include_non_public=False,
                actor_user_id=None,
                limit=10000,
                offset=0,
            )
            for article in self._rows(data):
                out.append(
                    {
                        "id": str(article["id"]),
                        "title": str(article["title"]),
                        "updated_at": str(article.get("updated_at") or ""),
                    }
                )
        # Blog general (artículos sin grupo).
        for article in self._rows(self._amigos_service().list_blog_articles(public_only=True, limit=10000, offset=0)):
            out.append(
                {
                    "id": str(article["id"]),
                    "title": str(article["title"]),
                    "updated_at": str(article.get("updated_at") or ""),
                }
            )
        return out

    # --- serialización -------------------------------------------------------

    @staticmethod
    def _str_or_none(value: object) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None

    def _amigos_group_read(self, row: dict[str, object]) -> AmigosGroupRead:
        links = [
            AmigosGroupLink(
                kind=str(x.get("kind") or ""),
                url=str(x.get("url") or ""),
                label=self._str_or_none(x.get("label")),
            )
            for x in self._store.list_amigos_group_links(str(row["id"]))
        ]
        return AmigosGroupRead(
            id=str(row["id"]),
            slug=str(row["slug"]),
            name=str(row["name"]),
            kind=str(row["kind"]),
            description=self._str_or_none(row.get("description")),
            image_url=self._str_or_none(row.get("image_url")),
            website=self._str_or_none(row.get("website")),
            email=self._str_or_none(row.get("email")),
            logo_url=self._str_or_none(row.get("logo_url")),
            links=links,
            status=str(row.get("status") or "active"),
            editorial_mode=str(row.get("editorial_mode") or "moderated"),
            created_at=str(row.get("created_at") or ""),
            updated_at=str(row.get("updated_at") or ""),
        )

    def _amigos_coral_read(self, row: dict[str, object]) -> AmigosCoralDetailsRead:
        def text(key: str) -> str | None:
            value = row.get(key)
            clean = str(value).strip() if value is not None else ""
            return clean or None

        count = row.get("member_count")
        rep = row.get("repertoire")
        langs = row.get("languages")
        places = row.get("places")
        return AmigosCoralDetailsRead(
            group_id=str(row.get("group_id") or ""),
            foundation_date=text("foundation_date"),
            dissolution_date=text("dissolution_date"),
            locality=text("locality"),
            region=text("region"),
            country_code=text("country_code"),
            venue=text("venue"),
            formation_type=text("formation_type"),
            member_count=int(str(count)) if count is not None else None,
            website=text("website"),
            public_email=text("public_email"),
            director_person_id=text("director_person_id"),
            director_label=text("director_label"),
            linked_entity=text("linked_entity"),
            repertoire=[str(v) for v in rep] if isinstance(rep, list) else [],
            languages=[str(v) for v in langs] if isinstance(langs, list) else [],
            places=[str(v) for v in places] if isinstance(places, list) else [],
        )

    def _amigos_member_read(self, row: dict[str, object]) -> AmigosMemberRead:
        return AmigosMemberRead(
            group_id=str(row["group_id"]),
            user_id=str(row["user_id"]),
            role=str(row.get("role") or "collaborator"),
            status=str(row.get("status") or "active"),
            created_at=str(row.get("created_at") or ""),
            updated_at=str(row.get("updated_at") or ""),
        )

    def _articles_read(self, rows: list[dict[str, object]]) -> list[AmigosArticleRead]:
        """Serializa artículos resolviendo cada grupo UNA sola vez (evita N+1 consultas)."""
        cache: dict[str, dict[str, object] | None] = {}
        out: list[AmigosArticleRead] = []
        for row in rows:
            group_id = str(row["group_id"])
            if group_id not in cache:
                cache[group_id] = self._amigos_service().get_group(group_id)
            out.append(self._amigos_article_read(row, group=cache[group_id]))
        return out

    def _amigos_article_read(
        self, row: dict[str, object], *, group: object = _GROUP_UNSET
    ) -> AmigosArticleRead:
        if group is _GROUP_UNSET:
            group = self._amigos_service().get_group(str(row["group_id"]))
        media_rows = row.get("media")
        media = [
            AmigosMediaRead(
                kind=str(m.get("kind") or ""),
                url=str(m.get("url") or ""),
                provider=self._str_or_none(m.get("provider")),
                video_id=self._str_or_none(m.get("video_id")),
                caption=self._str_or_none(m.get("caption")),
                credit=self._str_or_none(m.get("credit")),
                position=int(str(m.get("position") or 0)),
            )
            for m in (media_rows if isinstance(media_rows, list) else [])
            if isinstance(m, dict)
        ]
        group_row = group if isinstance(group, dict) else None
        return AmigosArticleRead(
            id=str(row["id"]),
            group_id=str(row["group_id"]),
            group_slug=str(group_row["slug"]) if group_row else None,
            group_name=str(group_row["name"]) if group_row else None,
            title=str(row["title"]),
            slug=str(row["slug"]),
            event_date=str(row.get("event_date") or ""),
            summary=self._str_or_none(row.get("summary")),
            body=str(row.get("body") or ""),
            cover_url=self._str_or_none(row.get("cover_url")),
            author_user_id=str(row.get("author_user_id") or ""),
            status=str(row.get("status") or "draft"),
            published_at=self._str_or_none(row.get("published_at")),
            created_at=str(row.get("created_at") or ""),
            updated_at=str(row.get("updated_at") or ""),
            media=media,
        )

    @staticmethod
    def _article_dict(article: AmigosArticleRead) -> dict[str, object]:
        return article.model_dump()
