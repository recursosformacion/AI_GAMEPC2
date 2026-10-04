"""Circuito de aportaciones (contributions) — primera capa funcional.

Alcance de este bloque: **solo `add_resource`** (`target_kind=representation`,
`target_id=representation_id`), ciclo de vida `draft → submitted → in_review →
accepted | rejected`, más `withdrawn`, y relaciones declaradas con validación independiente.

NO materializa nada en el catálogo: aceptar una aportación solo la marca `accepted`
(la materialización vía storage/`POST /api/admin/resources` es el bloque siguiente).

Persistencia vía el store operativo de osap-api (`_MysqlStore`/`MemoryStore`), que
implementa las cuatro tablas definidas por la migración preparada (no ejecutada).
"""

from __future__ import annotations

import json
from typing import Any

OPERATIONS = frozenset({"create_work", "add_representation", "add_resource"})
TARGET_KINDS = frozenset({"work", "representation", "resource"})
RELATION_KINDS = frozenset({"musical", "contribution"})
# Códigos de relación **de aportación** (los musicales son los roles existentes del catálogo).
CONTRIBUTION_RELATION_CODES = frozenset(
    {"aportante", "propietario_comparte", "fuente_declarada"}
)

# Estados del ciclo de vida.
STATUSES = frozenset(
    {"draft", "submitted", "in_review", "accepted", "rejected", "withdrawn"}
)
# Transiciones administrativas/de envío permitidas (origen -> destino).
_TRANSITIONS: dict[str, dict[str, str]] = {
    "submit": {"draft": "submitted"},
    "in_review": {"submitted": "in_review"},
    "accept": {"in_review": "accepted"},
    "reject": {"in_review": "rejected"},
}
_WITHDRAWABLE = frozenset({"draft", "submitted", "in_review", "accepted"})
_ARTIFACT_EDITABLE = frozenset({"draft", "submitted"})

# Operaciones que este bloque soporta (el resto queda explícitamente no soportado).
SUPPORTED_OPERATIONS = frozenset({"add_resource"})


class ContributionError(Exception):
    """Error controlado de una aportación (código HTTP + mensaje seguro)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ContributionService:
    def __init__(self, store: Any) -> None:
        self._store = store

    # --- alta ---------------------------------------------------------------

    def create(
        self,
        *,
        actor_user_id: str,
        operation: str,
        target_kind: str,
        target_id: str | None,
        declared_source: str | None,
        relations: list[dict[str, Any]] | None,
        representation_exists: Any,
    ) -> dict[str, object]:
        if operation not in SUPPORTED_OPERATIONS:
            raise ContributionError(
                422, "UNSUPPORTED_OPERATION", "Operación no soportada en este bloque"
            )
        if operation not in OPERATIONS or target_kind not in TARGET_KINDS:
            raise ContributionError(422, "INVALID_OPERATION", "Operación o destino inválidos")
        if operation == "add_resource" and target_kind != "representation":
            raise ContributionError(
                422, "INVALID_TARGET", "add_resource requiere target_kind=representation"
            )
        if not target_id or not str(target_id).strip():
            raise ContributionError(422, "TARGET_REQUIRED", "target_id es obligatorio")
        if representation_exists is not None and not representation_exists(str(target_id)):
            raise ContributionError(404, "REPRESENTATION_NOT_FOUND", "La representación no existe")

        clean_relations = [self._validate_relation(r) for r in (relations or [])]
        return dict(self._store.add_contribution(
            actor_user_id=actor_user_id,
            operation=operation,
            target_kind=target_kind,
            target_id=str(target_id),
            declared_source=declared_source,
            relations=clean_relations,
            actor=actor_user_id,
        ))

    def _validate_relation(self, relation: dict[str, Any]) -> dict[str, Any]:
        kind = str(relation.get("relation_kind") or "")
        code = str(relation.get("relation_code") or "").strip()
        if kind not in RELATION_KINDS:
            raise ContributionError(422, "INVALID_RELATION_KIND", "relation_kind inválido")
        if not code:
            raise ContributionError(422, "RELATION_CODE_REQUIRED", "relation_code es obligatorio")
        if kind == "contribution" and code not in CONTRIBUTION_RELATION_CODES:
            raise ContributionError(422, "INVALID_RELATION_CODE", "Código de aportación inválido")
        return {
            "relation_kind": kind,
            "relation_code": code,
            "person_id": relation.get("person_id"),
            "person_name": relation.get("person_name"),
        }

    # --- adjuntar artefacto -------------------------------------------------

    def attach_artifact(
        self,
        *,
        actor_user_id: str,
        contribution_id: int,
        file_id: int,
        kind: str | None,
        is_admin: bool,
    ) -> dict[str, object]:
        row = self._get_owned(actor_user_id, contribution_id, is_admin)
        if str(row["status"]) not in _ARTIFACT_EDITABLE:
            raise ContributionError(409, "INVALID_STATE", "No se pueden adjuntar artefactos en este estado")
        if not isinstance(file_id, int) or file_id <= 0:
            raise ContributionError(422, "INVALID_FILE_ID", "file_id inválido")
        if self._store.contribution_artifact_exists(contribution_id, file_id):
            raise ContributionError(409, "ARTIFACT_DUPLICATE", "Ese fichero ya está adjunto")
        self._store.add_contribution_artifact(
            contribution_id=contribution_id, file_id=file_id, kind=kind, actor=actor_user_id
        )
        result = self._store.get_contribution(contribution_id)
        assert result is not None
        return dict(result)

    # --- envío y retirada ---------------------------------------------------

    def submit(self, *, actor_user_id: str, contribution_id: int, is_admin: bool) -> dict[str, object]:
        row = self._get_owned(actor_user_id, contribution_id, is_admin)
        self._ensure_transition("submit", str(row["status"]))
        if str(row["operation"]) == "add_resource" and not self._store.list_contribution_artifacts(
            contribution_id
        ):
            raise ContributionError(422, "ARTIFACT_REQUIRED", "Falta adjuntar un fichero")
        return dict(
            self._store.set_contribution_status(
                contribution_id=contribution_id,
                status="submitted",
                reviewed_by=None,
                review_note=None,
                event_type="submitted",
                actor=actor_user_id,
            )
        )

    def withdraw(self, *, actor_user_id: str, contribution_id: int, is_admin: bool) -> dict[str, object]:
        row = self._get_owned(actor_user_id, contribution_id, is_admin)
        current = str(row["status"])
        if current not in _WITHDRAWABLE:
            raise ContributionError(409, "INVALID_TRANSITION", "No se puede retirar en este estado")
        return dict(
            self._store.set_contribution_status(
                contribution_id=contribution_id,
                status="withdrawn",
                reviewed_by=None,
                review_note=None,
                event_type="withdrawn",
                actor=actor_user_id,
            )
        )

    # --- consulta -----------------------------------------------------------

    def get(self, *, actor_user_id: str, contribution_id: int, is_admin: bool) -> dict[str, object] | None:
        row = self._store.get_contribution(contribution_id)
        if row is None:
            return None
        if not is_admin and str(row["actor_user_id"]) != actor_user_id:
            return None
        return dict(row)

    def list_mine(self, *, actor_user_id: str, limit: int, offset: int) -> tuple[list[dict[str, object]], int]:
        rows, total = self._store.list_contributions_by_actor(
            actor_user_id, limit=limit, offset=offset
        )
        return list(rows), int(total)

    def list_for_review(
        self, *, status: str | None, limit: int, offset: int
    ) -> tuple[list[dict[str, object]], int]:
        statuses = [status] if status else ["submitted", "in_review"]
        rows, total = self._store.list_contributions_for_review(
            statuses, limit=limit, offset=offset
        )
        return list(rows), int(total)

    # --- revisión administrativa -------------------------------------------

    def review(self, *, contribution_id: int, action: str, reviewer: str, note: str) -> dict[str, object] | None:
        row = self._store.get_contribution(contribution_id)
        if row is None:
            return None
        if action not in ("in_review", "accept", "reject"):
            raise ContributionError(422, "INVALID_ACTION", "Acción de revisión inválida")
        self._ensure_transition(action, str(row["status"]))
        target = _TRANSITIONS[action][str(row["status"])]
        return dict(
            self._store.set_contribution_status(
                contribution_id=contribution_id,
                status=target,
                reviewed_by=reviewer,
                review_note=note or None,
                event_type=f"status:{target}",
                actor=reviewer,
            )
        )

    def review_relation(
        self, *, contribution_id: int, relation_id: int, action: str, reviewer: str, note: str
    ) -> dict[str, object] | None:
        if action not in ("accept", "reject"):
            raise ContributionError(422, "INVALID_ACTION", "Acción de relación inválida")
        status = "accepted" if action == "accept" else "rejected"
        result = self._store.update_contribution_relation_validation(
            contribution_id=contribution_id,
            relation_id=relation_id,
            validation_status=status,
            validated_by=reviewer,
            actor=reviewer,
            note=note or None,
        )
        return dict(result) if result is not None else None

    # --- materialización (registro) -----------------------------------------

    def record_materialization(
        self, *, contribution_id: int, file_id: int, resource_id: int, actor: str
    ) -> None:
        """Registra (append-only) que un artifact se materializó como recurso de catálogo."""
        self._store.add_contribution_event(
            contribution_id=contribution_id,
            event_type="materialized",
            detail_json=json.dumps({"file_id": file_id, "resource_id": resource_id}),
            actor=actor,
        )

    def materialized_file_ids(self, contribution_id: int) -> set[int]:
        """`file_id`s ya materializados (idempotencia ante reintentos)."""
        result: set[int] = set()
        for event in self._store.list_contribution_events(contribution_id):
            if str(event.get("event_type")) != "materialized":
                continue
            try:
                detail = json.loads(str(event.get("detail_json") or "{}"))
            except ValueError:
                continue
            if isinstance(detail, dict) and detail.get("file_id") is not None:
                result.add(int(detail["file_id"]))
        return result

    # --- helpers ------------------------------------------------------------

    def _get_owned(self, actor_user_id: str, contribution_id: int, is_admin: bool) -> dict[str, object]:
        row = self._store.get_contribution(contribution_id)
        if row is None:
            raise ContributionError(404, "NOT_FOUND", "Aportación no encontrada")
        if not is_admin and str(row["actor_user_id"]) != actor_user_id:
            raise ContributionError(403, "FORBIDDEN", "No es tu aportación")
        return dict(row)

    def _ensure_transition(self, action: str, current: str) -> None:
        if current not in _TRANSITIONS.get(action, {}):
            raise ContributionError(
                409, "INVALID_TRANSITION", f"Transición no permitida: {current} → {action}"
            )
