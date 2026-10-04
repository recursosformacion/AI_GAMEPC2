"""PlatformApi: mixin de aportaciones (contributions).

Reutiliza el patrón de corrections: HTTP → mixin (auth) → `ContributionService` → store
operativo. El `actor_user_id` procede siempre de la identidad autenticada (nunca del body).
"""

from __future__ import annotations

from typing import Any

from src.osap.api.contracts import (
    ContributionArtifactRead,
    ContributionListRead,
    ContributionRead,
    ContributionRelationRead,
)
from src.osap.api.platform.core import PlatformApiCore
from src.osap.application.contributions import ContributionError, ContributionService
from src.osap.domain.votes import UnauthenticatedError
from src.osap.infrastructure.storage.contribution_uploads import StorageContributionError


class ContributionsMixin(PlatformApiCore):
    # --- usuario -------------------------------------------------------------

    def create_contribution(
        self,
        token: str | None,
        operation: str,
        target_kind: str,
        target_id: str | None,
        declared_source: str | None,
        relations: list[dict[str, Any]],
    ) -> ContributionRead:
        actor = self._require_user(token)
        row = self._contribution_service().create(
            actor_user_id=actor,
            operation=operation,
            target_kind=target_kind,
            target_id=target_id,
            declared_source=declared_source,
            relations=relations,
            representation_exists=self._representation_exists,
        )
        return self._contribution_read(row)

    def list_my_contributions(
        self, token: str | None, limit: int, offset: int
    ) -> ContributionListRead:
        actor = self._require_user(token)
        rows, total = self._contribution_service().list_mine(
            actor_user_id=actor, limit=limit, offset=offset
        )
        return ContributionListRead(items=[self._contribution_read(r) for r in rows], total=total)

    def get_contribution(self, token: str | None, contribution_id: int) -> ContributionRead | None:
        actor = self._require_user(token)
        row = self._contribution_service().get(
            actor_user_id=actor, contribution_id=contribution_id, is_admin=False
        )
        return self._contribution_read(row) if row else None

    def add_contribution_artifact(
        self, token: str | None, contribution_id: int, file_id: int, kind: str | None
    ) -> ContributionRead:
        actor = self._require_user(token)
        row = self._contribution_service().attach_artifact(
            actor_user_id=actor,
            contribution_id=contribution_id,
            file_id=file_id,
            kind=kind,
            is_admin=False,
        )
        return self._contribution_read(row)

    def upload_contribution(
        self,
        token: str | None,
        contribution_id: int,
        name: str,
        mime_type: str | None,
        data: bytes,
    ) -> ContributionRead:
        """Sube bytes a storage y los adjunta como artifact (no público)."""
        actor = self._require_user(token)
        service = self._contribution_service()
        row = service.get(actor_user_id=actor, contribution_id=contribution_id, is_admin=False)
        if row is None:
            raise ContributionError(404, "NOT_FOUND", "Aportación no encontrada")
        if str(row["status"]) not in ("draft", "submitted"):
            raise ContributionError(409, "INVALID_STATE", "No se puede subir en este estado")
        representation_id = row.get("target_id")
        if not representation_id:
            raise ContributionError(422, "TARGET_REQUIRED", "Falta la representación destino")
        client = self._container.storage_contributions()
        if client.representation_work_id(str(representation_id)) is None:
            raise ContributionError(404, "REPRESENTATION_NOT_FOUND", "La representación no existe")
        try:
            uploaded = client.upload_file(name=name, mime_type=mime_type, data=data)
        except StorageContributionError as exc:
            raise ContributionError(502, "STORAGE_UNAVAILABLE", "No se pudo subir a storage") from exc
        file_id = int(str(uploaded["id"]))
        updated = service.attach_artifact(
            actor_user_id=actor,
            contribution_id=contribution_id,
            file_id=file_id,
            kind=None,
            is_admin=False,
        )
        return self._contribution_read(updated)

    def submit_contribution(self, token: str | None, contribution_id: int) -> ContributionRead:
        actor = self._require_user(token)
        row = self._contribution_service().submit(
            actor_user_id=actor, contribution_id=contribution_id, is_admin=False
        )
        return self._contribution_read(row)

    def withdraw_contribution(self, token: str | None, contribution_id: int) -> ContributionRead:
        actor = self._require_user(token)
        row = self._contribution_service().withdraw(
            actor_user_id=actor, contribution_id=contribution_id, is_admin=False
        )
        return self._contribution_read(row)

    # --- administración ------------------------------------------------------

    def list_contributions_admin(
        self, token: str | None, status: str | None, limit: int, offset: int
    ) -> ContributionListRead:
        self._require_admin(token)
        rows, total = self._contribution_service().list_for_review(
            status=status, limit=limit, offset=offset
        )
        return ContributionListRead(items=[self._contribution_read(r) for r in rows], total=total)

    def get_contribution_admin(
        self, token: str | None, contribution_id: int
    ) -> ContributionRead | None:
        self._require_admin(token)
        row = self._contribution_service().get(
            actor_user_id="", contribution_id=contribution_id, is_admin=True
        )
        return self._contribution_read(row) if row else None

    def review_contribution(
        self, token: str | None, contribution_id: int, action: str, message: str
    ) -> ContributionRead | None:
        self._require_admin(token)
        reviewer = self._reviewer(token)
        row = self._contribution_service().review(
            contribution_id=contribution_id, action=action, reviewer=reviewer, note=message
        )
        return self._contribution_read(row) if row else None

    def review_contribution_relation(
        self,
        token: str | None,
        contribution_id: int,
        relation_id: int,
        action: str,
        message: str,
    ) -> ContributionRead | None:
        self._require_admin(token)
        reviewer = self._reviewer(token)
        service = self._contribution_service()
        service.review_relation(
            contribution_id=contribution_id,
            relation_id=relation_id,
            action=action,
            reviewer=reviewer,
            note=message,
        )
        row = service.get(actor_user_id="", contribution_id=contribution_id, is_admin=True)
        return self._contribution_read(row) if row else None

    # --- helpers -------------------------------------------------------------

    def _contribution_service(self) -> ContributionService:
        return ContributionService(self._store)

    def _require_user(self, token: str | None) -> str:
        principal = self._container.authenticator().resolve(token)
        user_id = getattr(principal, "user_id", None) if principal is not None else None
        if not user_id:
            raise UnauthenticatedError("Login required")
        return str(user_id)

    def _reviewer(self, token: str | None) -> str:
        principal = self._container.authenticator().resolve(token)
        user_id = getattr(principal, "user_id", None) if principal is not None else None
        if not user_id:
            raise UnauthenticatedError("Login required")
        return str(user_id)

    def _representation_exists(self, representation_id: str) -> bool:
        """Comprueba la representación real en storage (`GET /api/admin/representations/{id}`).

        Best-effort ante fallo de storage (no bloquea la creación si no se puede consultar);
        devuelve `False` solo cuando storage responde explícitamente que no existe.
        """
        try:
            client = self._container.storage_contributions()
        except RuntimeError:
            return True
        try:
            return client.representation_work_id(str(representation_id)) is not None
        except StorageContributionError:
            return True

    def _contribution_read(self, row: dict[str, object]) -> ContributionRead:
        cid = int(str(row["id"]))
        relations = [
            self._relation_read(r) for r in self._store.list_contribution_relations(cid)
        ]
        artifacts = [
            ContributionArtifactRead(
                id=int(str(a["id"])),
                file_id=int(str(a["file_id"])),
                kind=str(a["kind"]) if a.get("kind") else None,
            )
            for a in self._store.list_contribution_artifacts(cid)
        ]
        return ContributionRead(
            id=cid,
            actor_user_id=str(row["actor_user_id"]),
            operation=str(row["operation"]),
            target_kind=str(row["target_kind"]),
            target_id=str(row["target_id"]) if row.get("target_id") else None,
            declared_source=str(row["declared_source"]) if row.get("declared_source") else None,
            status=str(row["status"]),
            reviewed_by=str(row["reviewed_by"]) if row.get("reviewed_by") else None,
            reviewed_at=str(row["reviewed_at"]) if row.get("reviewed_at") else None,
            review_note=str(row["review_note"]) if row.get("review_note") else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            relations=relations,
            artifacts=artifacts,
        )

    def _relation_read(self, row: dict[str, object]) -> ContributionRelationRead:
        return ContributionRelationRead(
            id=int(str(row["id"])),
            relation_kind=str(row["relation_kind"]),
            relation_code=str(row["relation_code"]),
            person_id=str(row["person_id"]) if row.get("person_id") else None,
            person_name=str(row["person_name"]) if row.get("person_name") else None,
            validation_status=str(row["validation_status"]),
            materialized=bool(row.get("materialized")),
        )
