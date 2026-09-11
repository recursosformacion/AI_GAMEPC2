"""Serialización canónica y determinista de la resolución V2.1 → resolution_items (F3.4).

Garantiza la propiedad de estabilidad que exige la revisión de sesión:

    mismo resultado lógico  →  misma serialización  →  NO incrementa `revision`

La serialización no depende del orden de entrada de los candidatos ni de la representación
incidental de los objetos: las colecciones se ordenan de forma canónica y los flotantes se
redondean. Todo el JSON de persistencia se produce aquí (nunca en el dominio).
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, cast

from src.osap.domain.normalization import normalize_name

if TYPE_CHECKING:
    from typing import Any

    from src.osap.application.universe_resolution import ResolvedGroup
    from src.osap.domain.candidate_representation import CandidateRepresentation
    from src.osap.domain.evidence import EvidenceItem
    from src.osap.domain.ranking import RankingReason

_ROUND = 6


def resolved_group_payload(group: ResolvedGroup) -> dict[str, object]:
    """Payload canónico de un grupo resuelto (sin `status`: lo añade la policy)."""
    merged = group.merged.merged_descriptor
    title = merged.title or ""
    composer = merged.composer
    catalogue = merged.catalogue_number
    title_key = normalize_name(title)
    composer_key = normalize_name(composer) if composer else None

    normalized = {"title": title_key, "composer": composer_key, "catalog": catalogue}
    resolved = {
        "work": {"title": title, "catalog": catalogue},
        "composer": {"name": composer} if composer else None,
    }

    candidates = [
        _candidate_dict(rep, composer)
        for rep in sorted(group.group.representations, key=_representation_key)
    ]
    evidence = _evidence_list(group)
    confidence = round(group.score.score, _ROUND)

    return {
        "ref": {"title": title, "composer": composer, "catalogue": catalogue},
        "normalized": normalized,
        "resolved": resolved,
        "confidence": confidence,
        "candidates": candidates,
        "evidence": evidence,
    }


def item_id(payload: dict[str, object]) -> str:
    """Id estable de ítem desde el contenido canónico (no depende del orden de entrada)."""
    normalized = cast("dict[str, object]", payload["normalized"])
    key = f"{normalized.get('title') or ''}|{normalized.get('composer') or ''}|{normalized.get('catalog') or ''}"
    return "itm_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def canonical_json(payload: dict[str, object]) -> str:
    """JSON canónico (claves ordenadas, separadores estables) para persistencia/equality."""
    return json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, float):
        return round(value, _ROUND)
    return value


def _candidate_dict(rep: CandidateRepresentation, group_composer: str | None) -> dict[str, object]:
    return {
        "provider": rep.provider_id.value,
        "id": rep.remote_id or rep.candidate_id.value,
        "title": rep.work_descriptor.title,
        "composer": rep.work_descriptor.composer or group_composer,
        "catalogue": rep.work_descriptor.catalogue_number,
        "format": rep.format.value,
        "confidence": round(rep.confidence.value, _ROUND),
        "downloadable": rep.downloadable,
    }


def _representation_key(rep: CandidateRepresentation) -> tuple[str, str]:
    return (rep.provider_id.value, rep.remote_id or rep.candidate_id.value)


def _evidence_list(group: ResolvedGroup) -> list[dict[str, object]]:
    merge_evidence = [_evidence_item_to_dict(item) for item in group.merged.evidence]
    ranking_evidence = [_reason_to_dict(reason) for reason in group.score.reasons]
    combined = merge_evidence + ranking_evidence
    combined.sort(key=_evidence_sort_key)
    return combined


def _evidence_item_to_dict(item: EvidenceItem) -> dict[str, object]:
    return {
        "source": item.source.value,
        "code": item.code.value,
        "score": round(item.score, _ROUND),
        "strength": item.strength.value,
        "fields": {field.name: _canonical(field.value) for field in item.fields},
    }


def _reason_to_dict(reason: RankingReason) -> dict[str, object]:
    return {
        "source": "ranking",
        "code": reason.criterion.value,
        "field_score": round(reason.field_score, _ROUND),
        "weight": round(reason.weight, _ROUND),
        "contribution": round(reason.contribution, _ROUND),
    }


def _evidence_sort_key(item: dict[str, object]) -> tuple[Any, ...]:
    dumped = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
    return (str(item.get("source")), str(item.get("code")), dumped)


__all__ = ["canonical_json", "item_id", "resolved_group_payload"]
