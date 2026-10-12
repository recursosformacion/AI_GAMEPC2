"""Almacén operativo en memoria (fallback cuando MySQL no está disponible).

Parte de la división de `op_store.py` (F5.2): almacén en memoria puro, sin SQL.
`op_store.py` reexporta como facade para no romper imports.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime


def now() -> str:
    return datetime.now(UTC).isoformat()


class MemoryStore:
    """Almacén en memoria con la misma interfaz (fallback cuando MySQL no está)."""

    def __init__(self) -> None:
        self._suggestions: list[dict[str, object]] = []
        self._corrections: list[dict[str, object]] = []
        self._work_selections: dict[str, dict[str, object]] = {}
        self._providers: list[dict[str, object]] = []
        self._config: dict[str, str] = {}
        # Aportaciones (contributions): tabla(s) de la migración preparada.
        self._contributions: dict[int, dict[str, object]] = {}
        self._contribution_relations: list[dict[str, object]] = []
        self._contribution_events: list[dict[str, object]] = []
        self._contribution_artifacts: list[dict[str, object]] = []
        self._contrib_seq = 0
        self._contrib_rel_seq = 0
        self._contrib_evt_seq = 0
        self._contrib_art_seq = 0
        # «Los amigos»: grupos, membresías, artículos, recursos y auditoría.
        self._amigos_groups: dict[str, dict[str, object]] = {}
        self._amigos_members: dict[tuple[str, str], dict[str, object]] = {}
        self._amigos_articles: dict[str, dict[str, object]] = {}
        self._amigos_media: list[dict[str, object]] = []
        self._amigos_events: list[dict[str, object]] = []
        self._amigos_media_seq = 0
        self._amigos_evt_seq = 0
        # Especialización por tipo: ficha de coral (1:1 con el grupo) + facetas multivalor.
        self._amigos_coral_details: dict[str, dict[str, object]] = {}
        self._amigos_coral_attrs: list[dict[str, object]] = []
        self._amigos_coral_attr_seq = 0
        # Enlaces comunes del grupo (web/social): relación normalizada por tipo.
        self._amigos_group_links: list[dict[str, object]] = []
        self._amigos_group_link_seq = 0
        # Imágenes subidas (los ficheros viven en osap-storage; aquí su registro para servir).
        self._amigos_uploads: dict[int, dict[str, object]] = {}
        # Agenda: actuaciones/eventos y sus grupos participantes.
        self._amigos_actuaciones: dict[str, dict[str, object]] = {}
        self._amigos_actuacion_groups: list[dict[str, object]] = []
        # Autorizaciones editoriales (blog general / agenda): (scope, user_id).
        self._amigos_authorizations: dict[tuple[str, str], dict[str, object]] = {}

    def list_suggestions(self) -> list[dict[str, object]]:
        return list(self._suggestions)

    def add_suggestion(
        self,
        suggestion_id: str,
        name: str,
        source_type: str,
        location: str,
        mapping: dict[str, object],
        requested_by: str,
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "id": suggestion_id,
            "name": name,
            "type": source_type,
            "location": location,
            "mapping": json.dumps(mapping, ensure_ascii=False),
            "requested_by": requested_by,
            "status": "pending",
            "admin_message": None,
            "created_at": now(),
            "decided_at": None,
            "decided_by": None,
        }
        self._suggestions.append(row)
        return row

    def get_suggestion(self, suggestion_id: str) -> dict[str, object] | None:
        for row in self._suggestions:
            if row["id"] == suggestion_id:
                return row
        return None

    def resolve_suggestion(
        self, suggestion_id: str, status: str, message: str, decided_by: str
    ) -> dict[str, object] | None:
        for row in self._suggestions:
            if row["id"] == suggestion_id:
                row["status"] = status
                row["admin_message"] = message
                row["decided_at"] = now()
                row["decided_by"] = decided_by
                return row
        return None

    def pending_suggestion_count(self) -> int:
        return sum(1 for r in self._suggestions if r["status"] == "pending")

    def suggestion_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {"pending": 0, "approved": 0, "cancelled": 0, "total": 0}
        for r in self._suggestions:
            status = str(r.get("status") or "pending")
            counts[status] = counts.get(status, 0) + 1
            counts["total"] += 1
        return counts

    # --- correction / contact requests ----------------------------------------

    def list_corrections(self) -> list[dict[str, object]]:
        return list(self._corrections)

    def add_correction(
        self,
        correction_id: str,
        kind: str,
        entity_id: str | None,
        entity_provider: str | None,
        field: str | None,
        current_value: str | None,
        proposed_value: str | None,
        message: str,
        contact_email: str | None,
        requested_by: str | None,
        requested_by_name: str | None = None,
        requested_by_email: str | None = None,
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "id": correction_id,
            "kind": kind,
            "entity_id": entity_id,
            "entity_provider": entity_provider,
            "field": field,
            "current_value": current_value,
            "proposed_value": proposed_value,
            "message": message,
            "contact_email": contact_email,
            "requested_by": requested_by,
            "requested_by_name": requested_by_name,
            "requested_by_email": requested_by_email,
            "status": "pending",
            "admin_message": None,
            "created_at": now(),
            "decided_at": None,
            "decided_by": None,
        }
        self._corrections.append(row)
        return row

    def get_correction(self, correction_id: str) -> dict[str, object] | None:
        for row in self._corrections:
            if row["id"] == correction_id:
                return row
        return None

    def resolve_correction(
        self, correction_id: str, status: str, message: str, decided_by: str
    ) -> dict[str, object] | None:
        for row in self._corrections:
            if row["id"] == correction_id:
                row["status"] = status
                row["admin_message"] = message
                row["decided_at"] = now()
                row["decided_by"] = decided_by
                return row
        return None

    def pending_correction_count(self) -> int:
        return sum(1 for r in self._corrections if r["status"] == "pending")

    def list_providers(self) -> list[dict[str, object]]:
        return list(self._providers)

    def get_provider(self, provider_id: str) -> dict[str, object] | None:
        for row in self._providers:
            if row["provider_id"] == provider_id:
                return row
        return None

    def upsert_provider(
        self,
        provider_id: str,
        name: str,
        base_url: str | None = None,
        wired: bool = False,
        kind: str = "dynamic",
        config: dict[str, object] | None = None,
        description: dict[str, str] | str | None = None,
        endpoints: dict[str, object] | None = None,
        mapping: dict[str, object] | None = None,
        resources: dict[str, object] | None = None,
        transforms: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload = json.dumps(config or {}, ensure_ascii=False)
        for existing in self._providers:
            if existing["provider_id"] == provider_id:
                existing.update({
                    "name": name, "base_url": base_url, "wired": int(wired),
                    "config": payload, "description": description,
                    "endpoints": endpoints, "mapping": mapping,
                    "resources": resources, "transforms": transforms,
                })
                return existing
        row: dict[str, object] = {
            "provider_id": provider_id,
            "name": name,
            "kind": kind,
            "base_url": base_url,
            "wired": int(wired),
            "config": payload,
            "description": description,
            "endpoints": endpoints,
            "mapping": mapping,
            "resources": resources,
            "transforms": transforms,
            "created_at": now(),
        }
        self._providers.append(row)
        return row

    def delete_provider(self, provider_id: str) -> bool:
        before = len(self._providers)
        self._providers = [r for r in self._providers if r["provider_id"] != provider_id]
        return len(self._providers) < before

    def set_provider_wired(self, provider_id: str, wired: bool) -> dict[str, object] | None:
        for row in self._providers:
            if row["provider_id"] == provider_id:
                row["wired"] = int(wired)
                return row
        return None

    def get_config(self, key: str) -> str | None:
        return self._config.get(key)

    def set_config(self, key: str, value: str) -> None:
        self._config[key] = value

    def get_work_selection(self, work_id: str) -> dict[str, object] | None:
        return self._work_selections.get(work_id)

    def set_work_selection(self, work_id: str, selection_json: str) -> dict[str, object]:
        row: dict[str, object] = {
            "work_id": work_id,
            "selection_json": selection_json,
            "updated_at": now(),
        }
        self._work_selections[work_id] = row
        return row

    # --- contributions (aportaciones) -----------------------------------------

    def _append_event(
        self,
        contribution_id: int,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        relation_id: int | None,
        detail_json: str | None,
        actor: str | None,
    ) -> dict[str, object]:
        self._contrib_evt_seq += 1
        row: dict[str, object] = {
            "id": self._contrib_evt_seq,
            "contribution_id": int(contribution_id),
            "event_type": event_type,
            "from_status": from_status,
            "to_status": to_status,
            "relation_id": relation_id,
            "detail_json": detail_json,
            "actor": actor,
            "created_at": now(),
        }
        self._contribution_events.append(row)
        return row

    def add_contribution(
        self,
        *,
        actor_user_id: str,
        operation: str,
        target_kind: str,
        target_id: str | None,
        declared_source: str | None,
        payload_json: str | None = None,
        relations: list[dict[str, object]],
        actor: str | None,
    ) -> dict[str, object]:
        self._contrib_seq += 1
        cid = self._contrib_seq
        ts = now()
        row: dict[str, object] = {
            "id": cid,
            "actor_user_id": actor_user_id,
            "operation": operation,
            "target_kind": target_kind,
            "target_id": target_id,
            "declared_source": declared_source,
            "payload_json": payload_json,
            "status": "draft",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_note": None,
            "created_at": ts,
            "updated_at": ts,
        }
        self._contributions[cid] = row
        for rel in relations:
            self._contrib_rel_seq += 1
            self._contribution_relations.append(
                {
                    "id": self._contrib_rel_seq,
                    "contribution_id": cid,
                    "relation_kind": rel["relation_kind"],
                    "relation_code": rel["relation_code"],
                    "person_id": rel.get("person_id"),
                    "person_name": rel.get("person_name"),
                    "validation_status": "pending",
                    "validated_by": None,
                    "validated_at": None,
                    "materialized": 0,
                    "created_at": ts,
                    "updated_at": ts,
                }
            )
        self._append_event(cid, "created", None, "draft", None, None, actor)
        return row

    def get_contribution(self, contribution_id: int) -> dict[str, object] | None:
        return self._contributions.get(int(contribution_id))

    def list_contributions_by_actor(
        self, actor_user_id: str, *, limit: int, offset: int
    ) -> tuple[list[dict[str, object]], int]:
        rows = [r for r in self._contributions.values() if r["actor_user_id"] == actor_user_id]
        rows.sort(key=lambda r: int(str(r["id"])), reverse=True)
        return rows[offset : offset + limit], len(rows)

    def list_contributions_for_review(
        self, statuses: list[str], *, limit: int, offset: int
    ) -> tuple[list[dict[str, object]], int]:
        wanted = set(statuses)
        rows = [r for r in self._contributions.values() if r["status"] in wanted]
        rows.sort(key=lambda r: int(str(r["id"])))
        return rows[offset : offset + limit], len(rows)

    def list_contribution_relations(self, contribution_id: int) -> list[dict[str, object]]:
        cid = int(contribution_id)
        return [r for r in self._contribution_relations if r["contribution_id"] == cid]

    def list_contribution_artifacts(self, contribution_id: int) -> list[dict[str, object]]:
        cid = int(contribution_id)
        return [r for r in self._contribution_artifacts if r["contribution_id"] == cid]

    def list_contribution_events(self, contribution_id: int) -> list[dict[str, object]]:
        cid = int(contribution_id)
        return [r for r in self._contribution_events if r["contribution_id"] == cid]

    def add_contribution_event(
        self,
        *,
        contribution_id: int,
        event_type: str,
        from_status: str | None = None,
        to_status: str | None = None,
        relation_id: int | None = None,
        detail_json: str | None = None,
        actor: str | None = None,
    ) -> dict[str, object]:
        return self._append_event(
            int(contribution_id), event_type, from_status, to_status, relation_id, detail_json, actor
        )

    def contribution_artifact_exists(self, contribution_id: int, file_id: int) -> bool:
        cid, fid = int(contribution_id), int(file_id)
        return any(r["contribution_id"] == cid and r["file_id"] == fid for r in self._contribution_artifacts)

    def add_contribution_artifact(
        self, *, contribution_id: int, file_id: int, kind: str | None, actor: str | None
    ) -> dict[str, object]:
        self._contrib_art_seq += 1
        row: dict[str, object] = {
            "id": self._contrib_art_seq,
            "contribution_id": int(contribution_id),
            "file_id": int(file_id),
            "kind": kind,
            "created_at": now(),
        }
        self._contribution_artifacts.append(row)
        self._append_event(
            int(contribution_id),
            "artifact_added",
            None,
            None,
            None,
            json.dumps({"file_id": int(file_id)}),
            actor,
        )
        return row

    def set_contribution_status(
        self,
        *,
        contribution_id: int,
        status: str,
        reviewed_by: str | None,
        review_note: str | None,
        event_type: str,
        actor: str | None,
    ) -> dict[str, object] | None:
        row = self._contributions.get(int(contribution_id))
        if row is None:
            return None
        from_status = str(row["status"])
        row["status"] = status
        row["updated_at"] = now()
        if reviewed_by is not None:
            row["reviewed_by"] = reviewed_by
            row["reviewed_at"] = now()
        if review_note is not None:
            row["review_note"] = review_note
        self._append_event(int(contribution_id), event_type, from_status, status, None, None, actor)
        return row

    def update_contribution_relation_validation(
        self,
        *,
        contribution_id: int,
        relation_id: int,
        validation_status: str,
        validated_by: str | None,
        actor: str | None,
        note: str | None,
    ) -> dict[str, object] | None:
        cid, rid = int(contribution_id), int(relation_id)
        for rel in self._contribution_relations:
            if rel["id"] == rid and rel["contribution_id"] == cid:
                rel["validation_status"] = validation_status
                rel["validated_by"] = validated_by
                rel["validated_at"] = now()
                self._append_event(
                    cid,
                    "relation_validated",
                    None,
                    None,
                    rid,
                    json.dumps({"validation_status": validation_status, "note": note}),
                    actor,
                )
                return rel
        return None

    # --- «Los amigos»: grupos ------------------------------------------------

    def add_amigos_group(
        self,
        *,
        group_id: str,
        slug: str,
        name: str,
        kind: str,
        description: str | None,
        image_url: str | None,
        editorial_mode: str,
        created_by: str | None,
        website: str | None = None,
        email: str | None = None,
        logo_url: str | None = None,
    ) -> dict[str, object]:
        ts = now()
        row: dict[str, object] = {
            "id": group_id,
            "slug": slug,
            "name": name,
            "kind": kind,
            "description": description,
            "image_url": image_url,
            "website": website,
            "email": email,
            "logo_url": logo_url,
            "status": "active",
            "editorial_mode": editorial_mode,
            "created_by": created_by,
            "created_at": ts,
            "updated_at": ts,
        }
        self._amigos_groups[group_id] = row
        return row

    def get_amigos_group(self, group_id: str) -> dict[str, object] | None:
        row = self._amigos_groups.get(group_id)
        return dict(row) if row is not None else None

    def get_amigos_group_by_slug(self, slug: str) -> dict[str, object] | None:
        for row in self._amigos_groups.values():
            if row["slug"] == slug:
                return dict(row)
        return None

    def list_amigos_groups(
        self, *, active_only: bool = True, kind: str | None = None
    ) -> list[dict[str, object]]:
        rows = [
            dict(r)
            for r in self._amigos_groups.values()
            if (not active_only or str(r.get("status")) == "active")
            and (kind is None or str(r.get("kind")) == kind)
        ]
        rows.sort(key=lambda r: str(r.get("name") or "").lower())
        return rows

    def update_amigos_group(self, group_id: str, **changes: object) -> dict[str, object] | None:
        row = self._amigos_groups.get(group_id)
        if row is None:
            return None
        allowed = {"name", "description", "image_url", "editorial_mode", "status",
                    "website", "email", "logo_url"}
        for key, value in changes.items():
            if key in allowed:
                row[key] = value
        row["updated_at"] = now()
        return dict(row)

    # --- «Los amigos»: enlaces comunes del grupo (web/social) ----------------

    def replace_amigos_group_links(self, group_id: str, items: list[dict[str, object]]) -> None:
        self._amigos_group_links = [
            x for x in self._amigos_group_links if x["group_id"] != group_id
        ]
        for item in items:
            self._amigos_group_link_seq += 1
            self._amigos_group_links.append(
                {
                    "id": self._amigos_group_link_seq,
                    "group_id": group_id,
                    "kind": item.get("kind"),
                    "label": item.get("label"),
                    "url": item.get("url"),
                    "position": int(str(item.get("position") or 0)),
                }
            )

    def list_amigos_group_links(self, group_id: str) -> list[dict[str, object]]:
        rows = [dict(x) for x in self._amigos_group_links if x["group_id"] == group_id]
        rows.sort(key=lambda x: int(str(x.get("position") or 0)))
        return rows

    # --- «Los amigos»: imágenes subidas --------------------------------------

    def add_amigos_upload(
        self,
        *,
        file_id: int,
        group_id: str,
        mime_type: str | None,
        size_bytes: int | None,
        created_by: str | None,
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "file_id": int(file_id),
            "group_id": group_id,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "created_by": created_by,
            "created_at": now(),
        }
        self._amigos_uploads[int(file_id)] = row
        return dict(row)

    def get_amigos_upload(self, file_id: int) -> dict[str, object] | None:
        row = self._amigos_uploads.get(int(file_id))
        return dict(row) if row is not None else None

    # --- «Los amigos»: autorizaciones editoriales -----------------------------

    def set_amigos_authorization(
        self, *, user_id: str, scope: str, direct_publish: bool, granted_by: str | None
    ) -> dict[str, object]:
        ts = now()
        row: dict[str, object] = {
            "user_id": user_id,
            "scope": scope,
            "direct_publish": bool(direct_publish),
            "granted_by": granted_by,
            "created_at": ts,
            "updated_at": ts,
        }
        self._amigos_authorizations[(scope, user_id)] = row
        return dict(row)

    def get_amigos_authorization(self, scope: str, user_id: str) -> dict[str, object] | None:
        row = self._amigos_authorizations.get((scope, user_id))
        return dict(row) if row is not None else None

    def list_amigos_authorizations(self, scope: str) -> list[dict[str, object]]:
        rows = [dict(r) for r in self._amigos_authorizations.values() if r["scope"] == scope]
        rows.sort(key=lambda r: str(r.get("user_id")))
        return rows

    def delete_amigos_authorization(self, scope: str, user_id: str) -> None:
        self._amigos_authorizations.pop((scope, user_id), None)

    # --- «Los amigos»: agenda de actuaciones/eventos -------------------------

    def create_amigos_actuacion(
        self,
        *,
        actuacion_id: str,
        slug: str,
        editorial_status: str,
        author_user_id: str,
        fields: dict[str, object],
    ) -> dict[str, object]:
        ts = now()
        row: dict[str, object] = {
            "id": actuacion_id,
            "slug": slug,
            "editorial_status": editorial_status,
            "author_user_id": author_user_id,
            "published_at": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "review_note": None,
            "created_at": ts,
            "updated_at": ts,
        }
        row.update(fields)
        self._amigos_actuaciones[actuacion_id] = row
        return dict(row)

    def get_amigos_actuacion(self, actuacion_id: str) -> dict[str, object] | None:
        row = self._amigos_actuaciones.get(actuacion_id)
        return dict(row) if row is not None else None

    def get_amigos_actuacion_by_slug(self, slug: str) -> dict[str, object] | None:
        for row in self._amigos_actuaciones.values():
            if row["slug"] == slug:
                return dict(row)
        return None

    def update_amigos_actuacion(self, actuacion_id: str, **changes: object) -> dict[str, object] | None:
        row = self._amigos_actuaciones.get(actuacion_id)
        if row is None:
            return None
        allowed = {
            "title", "summary", "description", "image_url", "kind", "modality",
            "event_status", "starts_on", "starts_at", "ends_on", "ends_at", "timezone",
            "registration_deadline", "venue_name", "venue_address", "locality", "region",
            "country_code", "latitude", "longitude", "map_url", "organizer_name",
            "organizer_website", "event_url", "tickets_url", "price", "access_info",
            "public_contact", "organizer_group_id", "last_verified_on", "internal_notes",
        }
        for key, value in changes.items():
            if key in allowed:
                row[key] = value
        row["updated_at"] = now()
        return dict(row)

    def set_amigos_actuacion_status(
        self,
        *,
        actuacion_id: str,
        editorial_status: str,
        published_at: str | None,
        reviewed_by: str | None,
        review_note: str | None,
    ) -> dict[str, object] | None:
        row = self._amigos_actuaciones.get(actuacion_id)
        if row is None:
            return None
        row["editorial_status"] = editorial_status
        row["review_note"] = review_note
        if reviewed_by is not None:
            row["reviewed_by"] = reviewed_by
            row["reviewed_at"] = now()
        row["published_at"] = published_at
        row["updated_at"] = now()
        return dict(row)

    def list_amigos_actuaciones(
        self,
        *,
        editorial_statuses: list[str] | None,
        from_date: str | None,
        to_date: str | None,
        kind: str | None,
        locality: str | None,
        group_id: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        wanted = set(editorial_statuses) if editorial_statuses is not None else None
        group_ids: set[str] | None = None
        if group_id is not None:
            group_ids = {
                str(g["actuacion_id"])
                for g in self._amigos_actuacion_groups
                if g["group_id"] == group_id
            }
        rows: list[dict[str, object]] = []
        for raw in self._amigos_actuaciones.values():
            if wanted is not None and str(raw.get("editorial_status")) not in wanted:
                continue
            if group_ids is not None and str(raw["id"]) not in group_ids:
                continue
            if kind is not None and str(raw.get("kind")) != kind:
                continue
            if locality is not None and str(raw.get("locality") or "").lower() != locality.lower():
                continue
            start = str(raw.get("starts_on") or "")
            if from_date is not None and start < from_date:
                continue
            if to_date is not None and start > to_date:
                continue
            rows.append(dict(raw))
        rows.sort(key=lambda r: (str(r.get("starts_on") or ""), str(r.get("starts_at") or "")))
        return rows[offset : offset + limit], len(rows)

    def replace_amigos_actuacion_groups(
        self, actuacion_id: str, items: list[dict[str, object]]
    ) -> None:
        self._amigos_actuacion_groups = [
            x for x in self._amigos_actuacion_groups if x["actuacion_id"] != actuacion_id
        ]
        for item in items:
            self._amigos_actuacion_groups.append(
                {
                    "actuacion_id": actuacion_id,
                    "group_id": item.get("group_id"),
                    "role": item.get("role"),
                }
            )

    def list_amigos_actuacion_groups(self, actuacion_id: str) -> list[dict[str, object]]:
        rows = [
            dict(x) for x in self._amigos_actuacion_groups if x["actuacion_id"] == actuacion_id
        ]
        rows.sort(key=lambda x: (str(x.get("role")), str(x.get("group_id"))))
        return rows

    # --- «Los amigos»: membresías --------------------------------------------

    def set_amigos_member(
        self, *, group_id: str, user_id: str, role: str, status: str, granted_by: str | None
    ) -> dict[str, object]:
        key = (group_id, user_id)
        existing = self._amigos_members.get(key)
        ts = now()
        if existing is not None:
            existing.update({"role": role, "status": status, "granted_by": granted_by, "updated_at": ts})
            return dict(existing)
        row: dict[str, object] = {
            "group_id": group_id,
            "user_id": user_id,
            "role": role,
            "status": status,
            "granted_by": granted_by,
            "created_at": ts,
            "updated_at": ts,
        }
        self._amigos_members[key] = row
        return dict(row)

    def get_amigos_member(self, group_id: str, user_id: str) -> dict[str, object] | None:
        row = self._amigos_members.get((group_id, user_id))
        return dict(row) if row is not None else None

    def list_amigos_members(self, group_id: str) -> list[dict[str, object]]:
        rows = [dict(r) for r in self._amigos_members.values() if r["group_id"] == group_id]
        rows.sort(key=lambda r: (str(r.get("role")), str(r.get("user_id"))))
        return rows

    def list_amigos_memberships_by_user(self, user_id: str) -> list[dict[str, object]]:
        return [dict(r) for r in self._amigos_members.values() if r["user_id"] == user_id]

    # --- «Los amigos»: ficha de coral (especialización por tipo) -------------

    def get_amigos_coral_details(self, group_id: str) -> dict[str, object] | None:
        row = self._amigos_coral_details.get(group_id)
        return dict(row) if row is not None else None

    def upsert_amigos_coral_details(self, group_id: str, **fields: object) -> dict[str, object]:
        allowed = {
            "foundation_date", "dissolution_date", "locality", "region", "country_code",
            "venue", "formation_type", "member_count", "website", "public_email",
            "director_person_id", "director_label", "linked_entity",
        }
        ts = now()
        existing = self._amigos_coral_details.get(group_id)
        if existing is None:
            row: dict[str, object] = {"group_id": group_id, "created_at": ts, "updated_at": ts}
            for key in allowed:
                row[key] = None
            self._amigos_coral_details[group_id] = row
            existing = row
        for key, value in fields.items():
            if key in allowed:
                existing[key] = value
        existing["updated_at"] = ts
        return dict(existing)

    def replace_amigos_coral_attributes(
        self, group_id: str, items: list[dict[str, object]]
    ) -> None:
        self._amigos_coral_attrs = [a for a in self._amigos_coral_attrs if a["group_id"] != group_id]
        for item in items:
            self._amigos_coral_attr_seq += 1
            self._amigos_coral_attrs.append(
                {
                    "id": self._amigos_coral_attr_seq,
                    "group_id": group_id,
                    "facet": item.get("facet"),
                    "value": item.get("value"),
                    "position": int(str(item.get("position") or 0)),
                    "created_at": now(),
                }
            )

    def list_amigos_coral_attributes(self, group_id: str) -> list[dict[str, object]]:
        rows = [dict(a) for a in self._amigos_coral_attrs if a["group_id"] == group_id]
        rows.sort(key=lambda a: (str(a.get("facet")), int(str(a.get("position") or 0))))
        return rows

    # --- «Los amigos»: artículos ---------------------------------------------

    def create_amigos_article(
        self,
        *,
        article_id: str,
        group_id: str,
        title: str,
        slug: str,
        event_date: str,
        summary: str | None,
        body: str,
        cover_url: str | None,
        author_user_id: str,
        status: str,
        scope: str = "group",
    ) -> dict[str, object]:
        ts = now()
        row: dict[str, object] = {
            "id": article_id,
            "group_id": group_id,
            "scope": scope,
            "title": title,
            "slug": slug,
            "event_date": event_date,
            "summary": summary,
            "body": body,
            "cover_url": cover_url,
            "author_user_id": author_user_id,
            "status": status,
            "published_at": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "review_note": None,
            "created_at": ts,
            "updated_at": ts,
        }
        self._amigos_articles[article_id] = row
        return row

    def get_amigos_article(self, article_id: str) -> dict[str, object] | None:
        row = self._amigos_articles.get(article_id)
        return dict(row) if row is not None else None

    def get_amigos_article_by_slug(self, group_id: str, slug: str) -> dict[str, object] | None:
        for row in self._amigos_articles.values():
            if row["group_id"] == group_id and row["slug"] == slug:
                return dict(row)
        return None

    def get_amigos_article_by_scope_slug(self, scope: str, slug: str) -> dict[str, object] | None:
        for row in self._amigos_articles.values():
            if str(row.get("scope") or "group") == scope and row["slug"] == slug:
                return dict(row)
        return None

    def update_amigos_article(self, article_id: str, **changes: object) -> dict[str, object] | None:
        row = self._amigos_articles.get(article_id)
        if row is None:
            return None
        allowed = {"title", "event_date", "summary", "body", "cover_url", "slug"}
        for key, value in changes.items():
            if key in allowed:
                row[key] = value
        row["updated_at"] = now()
        return dict(row)

    def set_amigos_article_status(
        self,
        *,
        article_id: str,
        status: str,
        reviewed_by: str | None,
        review_note: str | None,
        published_at: str | None,
    ) -> dict[str, object] | None:
        row = self._amigos_articles.get(article_id)
        if row is None:
            return None
        row["status"] = status
        row["review_note"] = review_note
        if reviewed_by is not None:
            row["reviewed_by"] = reviewed_by
            row["reviewed_at"] = now()
        row["published_at"] = published_at
        row["updated_at"] = now()
        return dict(row)

    def list_amigos_articles(
        self,
        *,
        group_id: str | None,
        group_ids: list[str] | None = None,
        statuses: list[str] | None,
        scope: str | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        wanted = set(statuses) if statuses is not None else None
        allowed_groups = set(group_ids) if group_ids is not None else None
        rows = [
            dict(r)
            for r in self._amigos_articles.values()
            if (group_id is None or r["group_id"] == group_id)
            and (allowed_groups is None or str(r["group_id"]) in allowed_groups)
            and (wanted is None or str(r["status"]) in wanted)
            and (scope is None or str(r.get("scope") or "group") == scope)
        ]
        # Orden: fecha del evento DESC (más reciente primero), desempate por creación.
        rows.sort(key=lambda r: (str(r.get("event_date") or ""), str(r.get("created_at") or "")), reverse=True)
        return rows[offset : offset + limit], len(rows)

    def list_amigos_articles_by_author(
        self, author_user_id: str, *, limit: int, offset: int
    ) -> tuple[list[dict[str, object]], int]:
        rows = [
            dict(r) for r in self._amigos_articles.values() if r["author_user_id"] == author_user_id
        ]
        rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        return rows[offset : offset + limit], len(rows)

    # --- «Los amigos»: recursos audiovisuales --------------------------------

    def replace_amigos_media(self, article_id: str, items: list[dict[str, object]]) -> None:
        self._amigos_media = [m for m in self._amigos_media if m["article_id"] != article_id]
        for item in items:
            self._amigos_media_seq += 1
            self._amigos_media.append(
                {
                    "id": self._amigos_media_seq,
                    "article_id": article_id,
                    "kind": item.get("kind"),
                    "url": item.get("url"),
                    "provider": item.get("provider"),
                    "video_id": item.get("video_id"),
                    "caption": item.get("caption"),
                    "credit": item.get("credit"),
                    "position": int(str(item.get("position") or 0)),
                    "created_at": now(),
                }
            )

    def list_amigos_media(self, article_id: str) -> list[dict[str, object]]:
        rows = [dict(m) for m in self._amigos_media if m["article_id"] == article_id]
        rows.sort(key=lambda m: int(str(m.get("position") or 0)))
        return rows

    # --- «Los amigos»: auditoría ---------------------------------------------

    def add_amigos_event(
        self,
        *,
        group_id: str | None,
        article_id: str | None,
        event_type: str,
        actor: str | None,
        from_status: str | None = None,
        to_status: str | None = None,
        detail_json: str | None = None,
    ) -> dict[str, object]:
        self._amigos_evt_seq += 1
        row: dict[str, object] = {
            "id": self._amigos_evt_seq,
            "group_id": group_id,
            "article_id": article_id,
            "event_type": event_type,
            "actor": actor,
            "from_status": from_status,
            "to_status": to_status,
            "detail_json": detail_json,
            "created_at": now(),
        }
        self._amigos_events.append(row)
        return row

    def list_amigos_events(
        self, *, group_id: str | None, article_id: str | None
    ) -> list[dict[str, object]]:
        rows = [
            dict(e)
            for e in self._amigos_events
            if (group_id is None or e["group_id"] == group_id)
            and (article_id is None or e["article_id"] == article_id)
        ]
        rows.sort(key=lambda e: int(str(e.get("id") or 0)))
        return rows
