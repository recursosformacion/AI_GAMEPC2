"""DTO mappers, ejemplos de respuesta y helpers de soporte HTTP (F5.5-clean)."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any, cast

from src.osap.api.contracts import (
    ComposerCreationEvidenceResponse,
    ComposerDetailResponse,
    ComposerEvidenceResponse,
    ComposerIdentifierResponse,
    ComposerListResponse,
    ComposerResolveCandidateResponse,
    ComposerResolveEvidenceResponse,
    ComposerResolveResponse,
    ComposerStatisticsResponse,
    ComposerSummaryResponse,
    ComposerWorkRefResponse,
    ComposerWorksResponse,
    MergeComposersResultResponse,
    ResolutionItemResponse,
    ResolutionPolicy,
    ResolutionProgress,
    ResolutionResultsResponse,
    ResolutionSessionResponse,
    ResolvedComposerResponse,
    WorksNormalized,
    WorksResolved,
    WorkStatisticsResponse,
)
from src.osap.api.platform import VERSION

if TYPE_CHECKING:
    from src.osap.application.composer_resolution_engine import ResolutionDecision, ResolvedComposer

_EXTENSION = {"musicxml": ".musicxml", "pdf": ".pdf", "midi": ".mid"}


def _download_filename(info: dict[str, object]) -> str:
    composer = str(info.get("composer") or "")
    title = str(info.get("title") or "representation")
    catalogue = str(info.get("catalogue") or "")
    base = f"{composer} - {title}".strip(" -")
    if catalogue:
        base = f"{base} {catalogue}".strip()
    ext = _EXTENSION.get(str(info.get("format") or ""), ".bin")
    # El nombre va en la cabecera Content-Disposition (latin-1): sanear a ASCII seguro.
    safe = re.sub(r'[\\/:*?"<>|\u201c\u201d\u2018\u2019\u2013\u2014]+', "_", base)
    safe = safe.encode("ascii", "ignore").decode("ascii").strip(" .")
    return (safe or "representation") + ext


_MEDIA_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "musicxml": "application/vnd.recordare.musicxml+xml",
    "midi": "audio/midi",
}


def _media_type_for_format(fmt: str) -> str:
    return _MEDIA_TYPES.get(fmt, "application/octet-stream")


# Cabeceras para fetches server-side al storage/CDN propio. Cloudflare (R2 custom domain)
# responde 403 a User-Agents de librería (python-requests/curl); con UA de navegador sirve
# el fichero. El proxy de descarga de osap-api las usa.
_BROWSER_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

_TAGS = [
    {"name": "Searches", "description": "Create and retrieve searches."},
    {"name": "Jobs", "description": "Orchestrate long-running tasks."},
    {"name": "Providers", "description": "Provider state and capabilities."},
    {"name": "Knowledge", "description": "Learned knowledge (read-only)."},
    {"name": "Votes", "description": "Votación de obras y estadísticas agregadas."},
    {"name": "System", "description": "Health, version and statistics."},
    {"name": "Composers", "description": "Consulta pública de compositores y catálogos."},
    {"name": "Works", "description": "Obras, representaciones y descargas."},
    {"name": "Sources", "description": "Fuentes de catálogo y de sesión."},
    {"name": "Auth", "description": "Registro, verificación y OIDC."},
    {"name": "Admin", "description": "Mantenimiento y administración."},
    {"name": "Support", "description": "Contacto y correcciones de catálogo."},
]


def _request_id() -> str:
    return uuid.uuid4().hex


def _example(data: object) -> dict[str, Any]:
    return {"success": True, "request_id": "example-request-id", "data": data}


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "request_id": "example-request-id",
        "error": {"code": code, "message": message, "details": {}},
    }


def _resp(description: str, example: dict[str, Any]) -> dict[str, Any]:
    return {"description": description, "content": {"application/json": {"example": example}}}


_INVALID_QUERY_400 = _resp("Invalid query", _error("INVALID_QUERY", "Query cannot be empty"))


_INVALID_JOB_400 = _resp("Invalid job type", _error("INVALID_JOB_TYPE", "Job type cannot be empty"))


_NOT_FOUND_404 = _resp("Resource not found", _error("NOT_FOUND", "Resource not found"))


_VALIDATION_422 = _resp("Validation error", _error("VALIDATION", "Request validation failed"))


_INTERNAL_500 = _resp("Internal server error", _error("INTERNAL", "Unexpected server error"))


_SEARCH_CREATED_201 = _resp(
    "Search created",
    _example(
        {
            "search_id": "9f2c0a1b",
            "results": [
                {
                    "work": {
                        "work_id": "w1",
                        "title": "Ave Verum Corpus",
                        "composer": "Wolfgang Amadeus Mozart",
                        "catalogue": "KV 618",
                    },
                    "representation": {"provider": "imslp", "format": "musicxml", "confidence": 0.9},
                    "score": 0.9,
                    "evidence": [],
                }
            ],
        }
    ),
)


_SEARCH_GET_200 = _resp("Search retrieved", _SEARCH_CREATED_201["content"])


_JOB_CREATED_201 = _resp(
    "Job created",
    _example({"job_id": "job-1", "type": "provider-sync", "state": "completed", "progress": 100, "result": {}}),
)


_JOB_LIST_200 = _resp(
    "Jobs list",
    _example([{"job_id": "job-1", "type": "provider-sync", "state": "completed", "progress": 100, "result": {}}]),
)


_JOB_GET_200 = _resp("Job retrieved", _JOB_CREATED_201["content"])


_PROVIDER_LIST_200 = _resp(
    "Providers list",
    _example(
        [
            {
                "provider_id": "imslp",
                "name": "IMSLP",
                "available": True,
                "formats": ["musicxml", "pdf"],
                "last_sync": None,
            }
        ]
    ),
)


_PROVIDER_GET_200 = _resp(
    "Provider retrieved",
    _example(
        {
            "provider_id": "imslp",
            "name": "IMSLP",
            "available": True,
            "formats": ["musicxml", "pdf"],
            "last_sync": None,
        }
    ),
)


_KNOWLEDGE_OBSERVATIONS_200 = _resp(
    "Knowledge observations",
    _example(
        [
            {
                "execution_id": "e1",
                "source": "merge",
                "field": "title",
                "value": "Ave Verum K618",
                "provider": "imslp",
            }
        ]
    ),
)


_KNOWLEDGE_FACTS_200 = _resp(
    "Knowledge facts",
    _example([{"fact_type": "frequency", "field": "title", "value": "Ave Verum K618", "count": 2}]),
)


_KNOWLEDGE_SUGGESTIONS_200 = _resp(
    "Knowledge suggestions",
    _example(
        [
            {
                "suggestion_type": "add_alias",
                "field": "title",
                "source_value": "Ave Verum K618",
                "target_value": "Ave Verum Corpus KV 618",
                "reason": "observed 2 times",
            }
        ]
    ),
)


_HEALTH_200 = _resp("Health", _example({"status": "ok"}))


_READY_200 = _resp("Ready", _example({"status": "ready"}))


_LIVE_200 = _resp("Live", _example({"status": "live"}))


_VERSION_200 = _resp("Version", _example({"version": VERSION}))


_STATISTICS_200 = _resp(
    "Statistics",
    _example(
        {
            "providers": 5,
            "searches": 10,
            "jobs": 3,
            "knowledge_observations": 12,
            "knowledge_facts": 4,
            "knowledge_suggestions": 1,
        }
    ),
)


_SOURCES_LIST_200 = _resp(
    "Repository sources",
    _example(
        [
            {
                "source_id": "imslp",
                "name": "IMSLP",
                "type": "HTTP",
                "origin": "Official",
                "trust": "Verified",
                "status": "Online",
                "quality": 96,
                "quality_label": "Excellent",
                "updated_at": "2026-08-12 09:14 UTC",
            }
        ]
    ),
)


_SOURCE_GET_200 = _resp(
    "Repository source ficha",
    _example(
        {
            "source_id": "imslp",
            "name": "IMSLP",
            "type": "HTTP",
            "origin": "Official",
            "trust": "Verified",
            "status": "Online",
            "quality": 96,
            "quality_label": "Excellent",
            "updated_at": "2026-08-12 09:14 UTC",
            "representations": 128431,
            "works": 38912,
            "composers": 3281,
            "formats": ["MusicXML", "PDF", "MIDI"],
            "catalogues": ["BWV", "KV", "Hob.", "Op."],
            "duplicate_percent": 1.2,
            "coverage": ["Baroque", "Classical", "Romanticism"],
            "capabilities": ["Search", "Download", "MusicXML", "PDF", "MIDI", "Incremental Sync"],
            "description": "Official repository of public-domain scores.",
            "license": "Public Domain",
            "website": "https://imslp.org",
            "contact": "contact@imslp.org",
            "notes": "Very good Mozart coverage.",
            "observations": [{"date": "2026-07-18", "text": "Issues detected with Händel searches."}],
            "tags": ["Baroque", "Choral", "Public Domain"],
            "community_rating": 4,
            "reviews": 27,
            "searches": 3214,
            "downloads": 9321,
            "contributions": 42,
            "availability": 99.8,
        }
    ),
)


_UNAUTHORIZED_401 = _resp(
    "Unauthorized",
    _error("UNAUTHORIZED", "Missing or invalid access token"),
)


_FORBIDDEN_403 = _resp(
    "Forbidden",
    _error("FORBIDDEN", "Insufficient permissions"),
)


_SERVICE_UNAVAILABLE_503 = _resp(
    "Service unavailable",
    _error("SERVICE_UNAVAILABLE", "Service identity is not configured"),
)


_VOTE_201 = _resp(
    "Vote recorded",
    _example({"work_id": "w1", "vote": 5, "voted_at": "2026-08-06T10:00:00Z", "vote_day": "2026-08-06"}),
)


_DUPLICATE_VOTE_409 = _resp(
    "Duplicate vote",
    _error("DUPLICATE_VOTE", "Already voted for this work today"),
)


_INVALID_VOTE_422 = _resp(
    "Invalid vote",
    _error("INVALID_VOTE", "Vote must be between 1 and 5"),
)


_WORK_STATS_200 = _resp(
    "Work statistics",
    _example({"work_id": "w1", "vote_count": 37, "vote_average": 4.32}),
)


_COMPOSER_STATS_200 = _resp(
    "Composer statistics",
    _example({"composer_id": "mozart", "vote_count": 1523, "vote_average": 4.41}),
)


def _work_stats_dto(d: dict[str, object]) -> WorkStatisticsResponse:
    return WorkStatisticsResponse(
        work_id=cast("str", d["work_id"]),
        rating=cast("float | None", d.get("rating")),
        vote_count=cast("int", d["vote_count"]),
        work_count=cast("int", d.get("work_count") or 1),
    )


def _composer_stats_dto(d: dict[str, object]) -> ComposerStatisticsResponse:
    return ComposerStatisticsResponse(
        composer_id=cast("str", d["composer_id"]),
        rating=cast("float | None", d.get("rating")),
        vote_count=cast("int", d["vote_count"]),
        work_count=cast("int", d.get("work_count") or 0),
    )


def _composer_summary_dto(d: dict[str, object]) -> ComposerSummaryResponse:
    return ComposerSummaryResponse(
        id=cast("str", d.get("id") or ""),
        name=cast("str", d.get("name") or ""),
        status=cast("str", d.get("status") or "active"),
        aliases_count=cast("int", d.get("aliases_count") or 0),
        works_count=cast("int", d.get("works_count") or 0),
        review_status=cast("str | None", d.get("review_status")),
        visible=cast("bool", d.get("visible", True)),
        birth_year=cast("str | None", d.get("birth_year")),
        death_year=cast("str | None", d.get("death_year")),
    )


def _composer_list_dto(d: dict[str, object]) -> ComposerListResponse:
    items = d.get("items")
    raw_items = items if isinstance(items, list) else []
    # La consulta pública solo expone compositores visibles del Maestro.
    visible_items = [dict(i) for i in raw_items if isinstance(i, dict)
                     and bool(i.get("visible", True))]
    return ComposerListResponse(
        items=[_composer_summary_dto(i) for i in visible_items],
        total=cast("int", d.get("total") or 0),
    )


def _composer_identifier_dto(d: dict[str, object]) -> ComposerIdentifierResponse:
    return ComposerIdentifierResponse(
        composer_id=cast("str", d.get("composer_id") or ""),
        id_type=cast("str", d.get("id_type") or ""),
        id_value=cast("str", d.get("id_value") or ""),
        is_identity_anchor=cast("bool", d.get("is_identity_anchor", False)),
        source=cast("str", d.get("source") or "musicbrainz"),
        strength=cast("str | None", d.get("strength")),
        channels=_str_list(d.get("channels")),
    )


def _composer_build_evidence_dto(d: dict[str, object]) -> ComposerEvidenceResponse:
    return ComposerEvidenceResponse(
        composer_id=cast("str", d.get("composer_id") or ""),
        rule=cast("str", d.get("rule") or ""),
        decision=cast("str", d.get("decision") or ""),
        reason=cast("str", d.get("reason") or ""),
        anchor_type=cast("str", d.get("anchor_type") or "none"),
        anchor_value=cast("str", d.get("anchor_value") or "none"),
        channels=_list(d.get("channels")),
        identifiers_used=_list(d.get("identifiers_used")),
        matcher_version=cast("str", d.get("matcher_version") or ""),
        created_at=_iso_or_none(d.get("created_at")),
    )


def _composer_detail_dto(d: dict[str, object]) -> ComposerDetailResponse:
    aliases = d.get("aliases")
    raw_aliases = aliases if isinstance(aliases, list) else []
    evidence = d.get("creation_evidence")
    raw_evidence = evidence if isinstance(evidence, list) else []
    identifiers = d.get("identifiers")
    raw_identifiers = identifiers if isinstance(identifiers, list) else []
    build_evidence = d.get("evidence")
    raw_build_evidence = build_evidence if isinstance(build_evidence, list) else []
    key_works = d.get("biography_key_works")
    raw_key_works = key_works if isinstance(key_works, list) else []
    references = d.get("biography_references")
    raw_references = references if isinstance(references, list) else []
    return ComposerDetailResponse(
        id=cast("str", d.get("id") or ""),
        name=cast("str", d.get("name") or ""),
        status=cast("str", d.get("status") or "active"),
        aliases=[str(a) for a in raw_aliases if isinstance(a, str)],
        works_count=cast("int", d.get("works_count") or 0),
        merged_into=cast("str | None", d.get("merged_into")),
        merged_at=_iso_or_none(d.get("merged_at")),
        creation_evidence=[_composer_evidence_dto(dict(e)) for e in raw_evidence if isinstance(e, dict)],
        review_status=cast("str | None", d.get("review_status")),
        reviewed_at=_iso_or_none(d.get("reviewed_at")),
        visible=cast("bool", d.get("visible", True)),
        birth_year=cast("str | None", d.get("birth_year")),
        death_year=cast("str | None", d.get("death_year")),
        cluster_id=cast("str | None", d.get("cluster_id")),
        review_reason=cast("str | None", d.get("review_reason")),
        identifiers=[_composer_identifier_dto(dict(i)) for i in raw_identifiers if isinstance(i, dict)],
        evidence=[_composer_build_evidence_dto(dict(e)) for e in raw_build_evidence if isinstance(e, dict)],
        biography_summary=cast("str | None", d.get("biography_summary")),
        biography_era=cast("str | None", d.get("biography_era")),
        biography_nationality=cast("str | None", d.get("biography_nationality")),
        biography_key_works=[str(k) for k in raw_key_works if isinstance(k, str)],
        biography_key_fact=cast("str | None", d.get("biography_key_fact")),
        biography_references=[
            str(r) if isinstance(r, str) else str(r.get("title") or r.get("url") or r)
            for r in raw_references
            if isinstance(r, (dict, str))
        ],
    )


def _composer_evidence_dto(d: dict[str, object]) -> ComposerCreationEvidenceResponse:
    return ComposerCreationEvidenceResponse(
        composer_id=cast("str", d.get("composer_id") or ""),
        extracted_author=cast("str | None", d.get("extracted_author")),
        work_id=cast("int | None", d.get("work_id")),
        work_title=cast("str | None", d.get("work_title")),
        provider=cast("str | None", d.get("provider")),
        resource_reference=cast("str | None", d.get("resource_reference")),
    )


def _composer_works_dto(d: dict[str, object]) -> ComposerWorksResponse:
    items = d.get("items")
    raw_items = items if isinstance(items, list) else []
    return ComposerWorksResponse(
        items=[_composer_work_ref(dict(i)) for i in raw_items if isinstance(i, dict)],
        total=cast("int", d.get("total") or 0),
    )


def _composer_work_ref(d: dict[str, object]) -> ComposerWorkRefResponse:
    return ComposerWorkRefResponse(
        work_id=cast("int", d.get("work_id") or 0),
        title=cast("str | None", d.get("title")),
        composer_id=cast("str | None", d.get("composer_id")),
        tags=cast("str | None", d.get("tags")),
    )


def _composer_resolve_dto(d: ResolutionDecision) -> ComposerResolveResponse:
    return ComposerResolveResponse(
        status=d.status,
        composer=_resolved_composer_dto(d.composer) if d.composer is not None else None,
        confidence=d.confidence,
        input_quality=d.input_quality,
        candidates=[
            ComposerResolveCandidateResponse(
                name=c.composer.name,
                confidence=c.confidence,
                aliases=list(c.composer.aliases),
                external_ids=dict(c.composer.external_ids),
            )
            for c in d.candidates
        ],
        evidence=[
            ComposerResolveEvidenceResponse(
                provider=e.provider,
                type=e.kind,
                confidence=e.confidence,
                work_title=e.work_title,
                work_catalog=e.work_catalog,
            )
            for e in d.evidence
        ],
    )


def _resolved_composer_dto(c: ResolvedComposer) -> ResolvedComposerResponse:
    return ResolvedComposerResponse(
        name=c.name,
        aliases=list(c.aliases),
        external_ids=dict(c.external_ids),
    )


def _resolution_session_dto(data: dict[str, object]) -> ResolutionSessionResponse:
    return ResolutionSessionResponse(
        session_id=cast("str", data["session_id"]),
        status=cast("str", data["status"]),
        query=cast("str | None", data.get("query")),
        providers=cast("list[str]", data.get("providers") or []),
        policy=ResolutionPolicy.model_validate(data.get("policy") or {}),
        progress=ResolutionProgress.model_validate(data.get("progress") or {}),
          created_at=cast("str", data["created_at"]),
          updated_at=cast("str", data["updated_at"]),
          expires_at=cast("str", data["expires_at"]),
          error=cast("str | None", data.get("error")),
          selection=cast("dict[str, object] | None", data.get("selection")),
      )


def _resolution_item_dto(row: dict[str, object]) -> ResolutionItemResponse:
    normalized = row.get("normalized")
    resolved = row.get("resolved")
    return ResolutionItemResponse(
        id=cast("str", row["id"]),
        status=cast("str", row["status"]),
        resolution_stage=cast("str", row["resolution_stage"]),
        revision=cast("int", row["revision"]),
        normalized=WorksNormalized.model_validate(normalized) if isinstance(normalized, dict) else None,
        resolved=WorksResolved.model_validate(resolved) if isinstance(resolved, dict) else None,
        confidence=cast("float", row["confidence"]),
        input_quality=cast("str", row["input_quality"]),
        candidates=[
            ComposerResolveCandidateResponse.model_validate(c)
            for c in cast("list[dict[str, object]]", row.get("candidates") or [])
        ],
        evidence=[
            ComposerResolveEvidenceResponse.model_validate(e)
            for e in cast("list[dict[str, object]]", row.get("evidence") or [])
        ],
    )


def _resolution_results_dto(data: dict[str, object]) -> ResolutionResultsResponse:
    return ResolutionResultsResponse(
        session_id=cast("str", data["session_id"]),
        status=cast("str", data["status"]),
        resolution_stage=cast("str", data["resolution_stage"]),
        revision=cast("int", data["revision"]),
        page=cast("int", data["page"]),
        per_page=cast("int", data["per_page"]),
        total=cast("int", data["total"]),
        results=[_resolution_item_dto(r) for r in cast("list[dict[str, object]]", data.get("results") or [])],
    )


def _resolution_session_created_example() -> dict[str, object]:
    return {
        "session_id": "ses_9f2c0a1b",
        "status": "acquiring",
        "created_at": "2026-08-14T15:00:00.000000+00:00",
        "expires_at": "2026-08-14T15:30:00.000000+00:00",
    }


def _resolution_session_example() -> dict[str, object]:
    return {
        "session_id": "ses_9f2c0a1b",
        "status": "resolving",
        "query": "Mozart Ave Verum K.618",
        "providers": ["omr", "imslp", "musicbrainz", "mutopia"],
        "policy": {
            "max_results_to_acquire": 500,
            "max_pages_per_provider": 20,
            "max_duration_s": 120,
            "ttl_s": 1800,
        },
        "progress": {
            "acquired_pages": 12,
            "acquired_works": 490,
            "items_total": 127,
            "items_resolved": 90,
            "items_ambiguous": 20,
            "items_not_found": 17,
        },
        "created_at": "2026-08-14T15:00:00.000000+00:00",
        "updated_at": "2026-08-14T15:01:00.000000+00:00",
        "expires_at": "2026-08-14T15:30:00.000000+00:00",
        "error": None,
    }


def _resolution_results_example() -> dict[str, object]:
    return {
        "session_id": "ses_9f2c0a1b",
        "status": "resolving",
        "resolution_stage": "provisional",
        "revision": 2,
        "page": 1,
        "per_page": 25,
        "total": 127,
        "results": [],
    }


def _normalize_composer(raw: str) -> str:
    # Normalización determinista del texto recibido (NO resolución).
    return " ".join((raw or "").lower().split())


def _merge_result_dto(d: dict[str, object]) -> MergeComposersResultResponse:
    sources = d.get("sources_merged")
    raw_sources = sources if isinstance(sources, list) else []
    return MergeComposersResultResponse(
        target_id=cast("str", d.get("target_id") or ""),
        sources_merged=[str(s) for s in raw_sources if isinstance(s, str)],
        aliases_transferred=cast("int", d.get("aliases_transferred") or 0),
        works_moved=cast("int", d.get("works_moved") or 0),
        merge_operation_id=cast("str | None", d.get("merge_operation_id")),
    )


def _iso_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _str_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return None


def _list(value: object) -> list[object] | None:
    return value if isinstance(value, list) else None


def _standard_errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    by_code: dict[int | str, dict[str, Any]] = {
        422: _VALIDATION_422,
        500: _INTERNAL_500,
    }
    for code in codes:
        if code == 400:
            by_code[400] = _INVALID_QUERY_400
        elif code == 404:
            by_code[404] = _NOT_FOUND_404
    return by_code

