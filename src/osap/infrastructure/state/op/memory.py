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
