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
