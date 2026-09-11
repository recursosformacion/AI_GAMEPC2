"""Compositores: catálogo, fusión, aliases y resolución."""

from pydantic import ConfigDict

from .base import _Frozen


class ComposerSummaryResponse(_Frozen):
    id: str
    name: str
    status: str
    aliases_count: int = 0
    works_count: int = 0
    review_status: str | None = None
    visible: bool = True
    birth_year: str | None = None
    death_year: str | None = None


class ComposerListResponse(_Frozen):
    items: list[ComposerSummaryResponse] = []
    total: int = 0


class ComposerIdentifierResponse(_Frozen):
    composer_id: str = ""
    id_type: str = ""
    id_value: str = ""
    is_identity_anchor: bool = False
    source: str = "musicbrainz"
    strength: str | None = None
    channels: list[str] | None = None


class ComposerEvidenceResponse(_Frozen):
    composer_id: str = ""
    rule: str = ""
    decision: str = ""
    reason: str = ""
    anchor_type: str = "none"
    anchor_value: str = "none"
    channels: list[object] | None = None
    identifiers_used: list[object] | None = None
    matcher_version: str = ""
    created_at: str | None = None


class ComposerCreationEvidenceResponse(_Frozen):
    composer_id: str = ""
    extracted_author: str | None = None
    work_id: int | None = None
    work_title: str | None = None
    provider: str | None = None
    resource_reference: str | None = None


class ComposerDetailResponse(_Frozen):
    id: str
    name: str
    status: str
    aliases: list[str] = []
    works_count: int = 0
    merged_into: str | None = None
    merged_at: str | None = None
    creation_evidence: list[ComposerCreationEvidenceResponse] = []
    review_status: str | None = None
    reviewed_at: str | None = None
    visible: bool = True
    birth_year: str | None = None
    death_year: str | None = None
    cluster_id: str | None = None
    review_reason: str | None = None
    identifiers: list[ComposerIdentifierResponse] = []
    evidence: list[ComposerEvidenceResponse] = []
    biography_summary: str | None = None
    biography_era: str | None = None
    biography_nationality: str | None = None
    biography_key_works: list[str] = []
    biography_key_fact: str | None = None
    biography_references: list[str] = []


class ComposerWorkRefResponse(_Frozen):
    work_id: int
    title: str | None = None
    composer_id: str | None = None
    tags: str | None = None


class ComposerWorksResponse(_Frozen):
    items: list[ComposerWorkRefResponse] = []
    total: int = 0


class MergeComposersRequest(_Frozen):
    target_id: str
    sources: list[str]


class CreateComposerRequest(_Frozen):
    name: str


class CatalogueRead(_Frozen):
    id: int
    prefix: str
    composer: str
    catalogue_name: str
    creator: str
    ordering_criterion: str


class ReviewComposerRequest(_Frozen):
    review_status: str


class AddAliasRequest(_Frozen):
    alias: str


class MoveAliasRequest(_Frozen):
    target_composer_id: str
    from_composer_id: str


class SetAttributionRequest(_Frozen):
    composer_ids: list[str]
    attribution_type: str


class AliasResponse(_Frozen):
    id: int
    alias: str
    normalized_alias: str


class MoveAliasResultResponse(_Frozen):
    alias: AliasResponse


class PromoteAliasResultResponse(_Frozen):
    composer_id: str
    name: str


class SetAttributionResultResponse(_Frozen):
    works_affected: int


class MergeComposersResultResponse(_Frozen):
    target_id: str
    sources_merged: list[str] = []
    aliases_transferred: int = 0
    works_moved: int = 0
    merge_operation_id: str | None = None


# --- resolución de identidad de compositor (v1) -------------------------------


class ComposerResolveComposer(_Frozen):
    name: str


class ComposerResolveWork(_Frozen):
    title: str
    catalog: str | None = None
    year: int | None = None


class ComposerResolveSource(_Frozen):
    provider: str | None = None
    source_work_id: str | None = None


class ComposerResolveRepresentation(_Frozen):
    title: str
    provider: str
    format: str


class ComposerResolveRequest(_Frozen):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "work": {"title": "Song to the Auspicious Cloud - Second Version", "catalog": "192128"},
                    "composer": {"name": "ä æ R Z H çèª"},
                },
                {"work": {"title": "Song to the Auspicious Cloud - Second Version"}},
            ]
        },
    )
    # La obra es la señal principal: `work.title` es obligatorio.
    work: ComposerResolveWork
    composer: ComposerResolveComposer | None = None
    source: ComposerResolveSource | None = None
    representations: list[ComposerResolveRepresentation] = []


class ResolvedComposerResponse(_Frozen):
    name: str
    aliases: list[str] = []
    external_ids: dict[str, str] = {}


class ComposerResolveEvidenceResponse(_Frozen):
    provider: str
    type: str
    confidence: float
    work_title: str | None = None
    work_catalog: str | None = None


class ComposerResolveCandidateResponse(_Frozen):
    name: str
    confidence: float
    aliases: list[str] = []
    external_ids: dict[str, str] = {}


class ComposerResolveResponse(_Frozen):
    status: str  # resolved | ambiguous | not_found
    composer: ResolvedComposerResponse | None = None
    confidence: float = 0.0
    input_quality: str = "normal"  # normal | suspicious | corrupt_or_suspicious
    candidates: list[ComposerResolveCandidateResponse] = []
    evidence: list[ComposerResolveEvidenceResponse] = []


# --- resolución de obras en lote (v1) ----------------------------------------


