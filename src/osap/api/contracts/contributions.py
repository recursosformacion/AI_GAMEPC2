"""Contratos de aportaciones (contributions) — gestión del ciclo de vida (bloque actual).

Solo `add_resource` está habilitado en este bloque:
`operation=add_resource`, `target_kind=representation`, `target_id=representation_id`.

Las relaciones declaradas (musicales | de aportación) se validan por separado del estado de
la aportación. `materialized` permanece 0: nada se escribe aún en el catálogo.
"""

from __future__ import annotations

from .base import _Frozen


class ContributionRelationRequest(_Frozen):
    """Relación declarada por el usuario (varias por aportación)."""

    relation_kind: str  # musical | contribution
    relation_code: str  # musical: slug de rol; contribution: aportante|propietario_comparte|fuente_declarada
    person_id: str | None = None
    person_name: str | None = None


class ContributionCreateRequest(_Frozen):
    operation: str
    target_kind: str
    target_id: str | None = None
    declared_source: str | None = None
    payload: dict[str, object] = {}
    relations: list[ContributionRelationRequest] = []


class ContributionArtifactRequest(_Frozen):
    file_id: int
    kind: str | None = None


class ContributionReviewRequest(_Frozen):
    action: str  # in_review | accept | reject
    message: str = ""


class ContributionRelationReviewRequest(_Frozen):
    action: str  # accept | reject
    message: str = ""


class ContributionRelationRead(_Frozen):
    id: int
    relation_kind: str
    relation_code: str
    person_id: str | None = None
    person_name: str | None = None
    validation_status: str
    materialized: bool = False


class ContributionArtifactRead(_Frozen):
    id: int
    file_id: int
    kind: str | None = None


class ContributionEventRead(_Frozen):
    id: int
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    relation_id: int | None = None
    actor: str | None = None
    created_at: str


class ContributionRead(_Frozen):
    id: int
    actor_user_id: str
    operation: str
    target_kind: str
    target_id: str | None = None
    declared_source: str | None = None
    status: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_note: str | None = None
    created_at: str
    updated_at: str
    relations: list[ContributionRelationRead] = []
    artifacts: list[ContributionArtifactRead] = []


class ContributionListRead(_Frozen):
    items: list[ContributionRead]
    total: int
