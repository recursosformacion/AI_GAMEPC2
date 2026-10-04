"""PlatformApi: mixin de aportaciones (contributions).

Reutiliza el patrón de corrections: HTTP → mixin (auth) → `ContributionService` → store
operativo. El `actor_user_id` procede siempre de la identidad autenticada (nunca del body).
"""

from __future__ import annotations

import json
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
        payload: dict[str, Any] | None = None,
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
            work_exists=self._work_exists,
            payload=payload,
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
        operation = str(row.get("operation"))
        target_id = row.get("target_id")
        client = self._container.storage_contributions()
        if operation == "add_resource":
            if not target_id:
                raise ContributionError(422, "TARGET_REQUIRED", "Falta la representación destino")
            if client.representation_work_id(str(target_id)) is None:
                raise ContributionError(
                    404, "REPRESENTATION_NOT_FOUND", "La representación no existe"
                )
        elif operation == "add_representation":
            if not target_id:
                raise ContributionError(422, "TARGET_REQUIRED", "Falta la obra destino")
            if not client.work_exists(str(target_id)):
                raise ContributionError(404, "WORK_NOT_FOUND", "La obra no existe")
        # create_work: no hay destino previo que validar
        try:
            uploaded = client.upload_file(name=name, mime_type=mime_type, data=data)
        except StorageContributionError as exc:
            raise ContributionError(502, "STORAGE_UNAVAILABLE", "No se pudo subir a storage") from exc
        file_id = int(str(uploaded["id"]))
        updated = service.attach_artifact(
            actor_user_id=actor,
            contribution_id=contribution_id,
            file_id=file_id,
            kind=self._resource_type(name, mime_type),
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
        service = self._contribution_service()
        if action == "accept":
            current = service.get(
                actor_user_id="", contribution_id=contribution_id, is_admin=True
            )
            if current is None:
                return None
            # Materializa PRIMERO; si storage falla, la aportación NO pasa a accepted.
            self._materialize(contribution_id, current, reviewer)
        row = service.review(
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

    @staticmethod
    def _resource_type(name: str, mime_type: str | None) -> str:
        """Tipo de recurso de catálogo a partir del nombre/mime (para la materialización)."""
        lowered = (name or "").lower()
        if lowered.endswith(".mxl"):
            return "MXL"
        if lowered.endswith((".musicxml", ".xml")):
            return "MusicXML"
        if lowered.endswith(".pdf") or mime_type == "application/pdf":
            return "PDF"
        if lowered.endswith((".mid", ".midi")):
            return "MIDI"
        if lowered.endswith(".mp3"):
            return "MP3"
        if mime_type == "application/vnd.recordare.musicxml+xml":
            return "MusicXML"
        return "score"

    def _materialize(
        self, contribution_id: int, row: dict[str, object], reviewer: str
    ) -> None:
        """Materializa la aportación al aceptar, según su operación. Idempotente por evento."""
        operation = str(row.get("operation"))
        payload = self._load_payload(row.get("payload_json"))
        client = self._container.storage_contributions()
        try:
            if operation == "add_resource":
                rep_raw = str(row.get("target_id") or "")
                work_id = client.representation_work_id(rep_raw)
                if work_id is None:
                    raise ContributionError(
                        404, "REPRESENTATION_NOT_FOUND", "La representación no existe"
                    )
                self._create_resources(
                    client, contribution_id, work_id, int(rep_raw), reviewer
                )
            elif operation == "add_representation":
                work_id = int(str(row.get("target_id")))
                representation_id = self._create_representation(client, work_id, payload)
                self._create_resources(
                    client, contribution_id, work_id, representation_id, reviewer
                )
            elif operation == "create_work":
                work_id = client.create_work(
                    title=str(payload.get("title") or ""),
                    origin=str(payload.get("origin") or ""),
                    license=payload.get("license"),
                    song_name=payload.get("song_name"),
                )
                representation_id = self._create_representation(client, work_id, payload)
                self._create_resources(
                    client, contribution_id, work_id, representation_id, reviewer
                )
            else:
                raise ContributionError(422, "UNSUPPORTED_OPERATION", "Operación no soportada")
        except StorageContributionError as exc:
            raise ContributionError(
                502, "STORAGE_UNAVAILABLE", "No se pudo materializar en storage"
            ) from exc

    def _create_representation(
        self, client: Any, work_id: int, payload: dict[str, Any]
    ) -> int:
        created = client.create_representation(
            works_id=work_id,
            origin=str(payload.get("origin") or ""),
            rep_type=str(payload.get("type") or ""),
            license=payload.get("license"),
            source_name=payload.get("source_name"),
            origin_id=payload.get("origin_id"),
        )
        return int(str(created))

    def _create_resources(
        self,
        client: Any,
        contribution_id: int,
        work_id: int,
        representation_id: int,
        reviewer: str,
    ) -> None:
        artifacts = list(self._store.list_contribution_artifacts(contribution_id))
        if not artifacts:
            raise ContributionError(422, "ARTIFACT_REQUIRED", "No hay fichero que materializar")
        service = self._contribution_service()
        done = service.materialized_file_ids(contribution_id)
        for artifact in artifacts:
            file_id = int(str(artifact["file_id"]))
            if file_id in done:
                continue
            created = client.create_resource(
                work_id=work_id,
                representation_id=representation_id,
                resource_type=str(artifact.get("kind") or "score"),
                name=f"Contribution {contribution_id}",
                status="stored",
                file_id=file_id,
            )
            service.record_materialization(
                contribution_id=contribution_id,
                file_id=file_id,
                resource_id=int(str(created["id"])),
                work_id=work_id,
                actor=reviewer,
            )

    @staticmethod
    def _load_payload(raw: object) -> dict[str, Any]:
        try:
            data = json.loads(str(raw or "{}"))
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

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

    def _work_exists(self, work_id: str) -> bool:
        """Comprueba la obra real en storage (`GET /api/admin/works/{id}`), best-effort."""
        try:
            client = self._container.storage_contributions()
        except RuntimeError:
            return True
        try:
            return client.work_exists(str(work_id))
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
