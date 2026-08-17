"""FASE 3 — reconstrucción del universo y matching provisional.

Reconstruye el universo exclusivamente desde `provider_results.payload` (sin HTTP) y
produce `resolution_items` de forma **determinista**: el mismo universo → el mismo
resultado, independientemente del momento o de la llamada HTTP. Aún no se toca el
algoritmo de confianza (eso es FASE 4).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.infrastructure.resolution.work_ranker import decide

if TYPE_CHECKING:
    from src.osap.infrastructure.state.resolution_store import _MemoryStore


def rebuild_universe(store: _MemoryStore, session_id: str) -> list[dict[str, object]]:
    """Lista de `{provider, work}` construida solo desde `provider_results` adquiridos."""
    universe: list[dict[str, object]] = []
    for row in store.list_all_provider_results(session_id):
        try:
            works = json.loads(str(row.get("payload_json") or "[]"))
        except ValueError:
            works = []
        provider = str(row.get("provider") or "?")
        for work in works:
            if isinstance(work, dict):
                universe.append({"provider": provider, "work": work})
    return universe


class IUniverseMatcher(Protocol):
    def match(self, universe: list[dict[str, object]]) -> list[dict[str, object]]:
        ...


@dataclass(frozen=True)
class _Candidate:
    provider: str
    identity: dict[str, object]
    confidence: float
    composer: str | None = None
    # Trazabilidad de procedencia del compositor (FASE 5.8): de dónde salió realmente.
    composer_source: str | None = None  # proveedor que lo aportó
    composer_field: str | None = None   # "composer" (campo) | "title" (incrustado en título)
    composer_raw: str | None = None     # valor crudo antes de normalizar
    inferred: bool = False              # True solo si OSAP lo generó (nunca ahora)


class SimpleUniverseMatcher:
    """Agrupa el universo por título normalizado (+ compositor) de forma determinista.

    Cada grupo (obra distinta) → un `resolution_item`. El estado es un heurístico
    provisional (`resolved` si hay compositor, si no `ambiguous`); la decisión de
    confianza definitiva se deja para FASE 4.
    """

    def match(self, universe: list[dict[str, object]]) -> list[dict[str, object]]:
        """Agrupa por título (ignorando el compositor faltante) y recupera el compositor
        desde el título o desde otros registros del mismo grupo.

        Principio: `composer=None` no es anónimo — es desconocido. Si al menos un registro
        de la obra (mismo título) aporta un compositor, el grupo lo adopta; si ninguno,
        la obra queda identificada pero con compositor desconocido (ambiguous, no not_found).
        """
        groups: dict[str, list[_Candidate]] = {}
        composers_by_group: dict[str, dict[str, str]] = {}
        evidence_by_group: dict[str, dict[str, dict[str, object]]] = {}
        for u in universe:
            identity = _as_identity(u.get("work"))
            title = str(identity.get("title") or "Unknown")
            provider = str(u.get("provider") or "?")
            composer = identity.get("composer")
            composer = str(composer).strip() if composer else None
            composer_field = None
            composer_raw = None
            composer_source_text = None
            if not composer:
                # El compositor puede estar incrustado en el título (evidencia de fuente).
                raw_title = title
                title, composer = MetadataNormalizer.extract_composer_from_title(title)
                if composer:
                    composer_field = "title"
                    composer_raw = composer  # valor extraído (antes de normalizar)
                    composer_source_text = raw_title  # de qué título salió
            else:
                composer_field = "composer"
                composer_raw = composer
            # Clave de identidad de obra (FASE 5.7.2): elimina ruido catalográfico/artículo
            # y usa el compositor solo como evidencia de atribución. Nunca asume anónimo.
            comp_title = MetadataNormalizer.normalize_title_with_trace(title, composer or None).key
            candidate = _Candidate(
                provider=provider,
                identity=identity,
                confidence=_confidence(identity),
                composer=composer,
                composer_source=provider if composer else None,
                composer_field=composer_field,
                composer_raw=composer_raw,
                inferred=False,  # OSAP no infiere atribución (ADR-0034).
            )
            groups.setdefault(comp_title, []).append(candidate)
            if composer:
                comp = MetadataNormalizer.comparison_composer(composer)
                composers_by_group.setdefault(comp_title, {})[comp] = composer
                evidence_by_group.setdefault(comp_title, {})[comp] = {
                    "source": provider,
                    "field": composer_field,
                    "raw_value": composer_raw,
                    "source_text": composer_source_text,
                    "inferred": False,
                }

        items: list[dict[str, object]] = []
        for key in sorted(groups):
            candidates = groups[key]
            candidates.sort(key=lambda c: (c.provider, str(c.identity.get("id") or "")))
            best = max(candidates, key=lambda c: c.confidence)
            distinct = [c for c in composers_by_group.get(key, {}) if c]
            group_composer = None
            composer_evidence = None
            if len(distinct) == 1:
                group_composer = composers_by_group[key][distinct[0]]
                composer_evidence = evidence_by_group.get(key, {}).get(distinct[0])
            # Si hay varios compositores distintos para el mismo título -> ambiguous (no decidir).
            items.append(self._item(key, candidates, best, group_composer, composer_evidence))
        return items

    @staticmethod
    def _item(
        key: str,
        candidates: list[_Candidate],
        best: _Candidate,
        group_composer: str | None,
        composer_evidence: dict[str, object] | None = None,
    ) -> dict[str, object]:
        identity = best.identity
        title = str(identity.get("title") or "Unknown")
        catalogue = identity.get("catalogue")
        comp_composer = MetadataNormalizer.comparison_composer(group_composer) if group_composer else ""
        clean_display = (
            MetadataNormalizer.clean_display_title(title, group_composer) if group_composer else title
        )
        confidence = best.confidence
        candidate_dicts = [
            {
                "provider": c.provider,
                "confidence": c.confidence,
                "identity": {**c.identity, "composer": c.composer or group_composer},
            }
            for c in candidates
        ]
        decision = decide(candidate_dicts)
        status = decision.status
        matching_providers = decision.ranking.matching_providers
        fingerprint = hashlib.sha1(key.encode()).hexdigest()[:16]  # noqa: S324
        return {
            "id": f"itm_{fingerprint}",
            "ref": {"title": title, "composer": group_composer, "catalogue": catalogue},
            "status": status,
            "normalized": {
                "title_raw": title,
                "title": key,
                "composer_raw": group_composer,
                "composer": comp_composer or None,
                "catalog": catalogue,
            },
            "resolved": {
                "work": {"title": clean_display, "catalog": catalogue},
                "composer": {"name": comp_composer} if comp_composer else None,
            },
            "composer_evidence": composer_evidence,  # procedencia de la atribución
            "confidence": confidence,
            "candidates": [
                {
                    "provider": c.provider,
                    "id": c.identity.get("id"),
                    "title": c.identity.get("title"),
                    "composer": c.composer or group_composer,
                    "catalogue": c.identity.get("catalogue"),
                    "confidence": c.confidence,
                    "matching_providers": matching_providers,
                    "title_score": _exact_title(c, best),
                    "catalogue_score": _exact_catalogue(c, best),
                    "composer_score": _exact_composer(c, best),
                    "final_score": c.confidence,
                }
                for c in candidates
            ],
            "evidence": [
                {"provider": c.provider, "kind": "universe_match", "confidence": c.confidence}
                for c in candidates
            ]
            + [
                {
                    "kind": "decision",
                    "reason": decision.reason,
                    "margin": decision.ranking.margin,
                    "best_score": decision.ranking.best_score,
                    "second_score": decision.ranking.second_score,
                }
            ],
        }


def _exact_title(a: _Candidate, b: _Candidate) -> float:
    at = MetadataNormalizer.comparison_title(str(a.identity.get("title") or ""), str(a.identity.get("composer") or ""))
    bt = MetadataNormalizer.comparison_title(str(b.identity.get("title") or ""), str(b.identity.get("composer") or ""))
    return 1.0 if at and at == bt else 0.0


def _exact_catalogue(a: _Candidate, b: _Candidate) -> float:
    av = str(a.identity.get("catalogue") or "").strip().lower()
    bv = str(b.identity.get("catalogue") or "").strip().lower()
    return 1.0 if av and av == bv else 0.0


def _exact_composer(a: _Candidate, b: _Candidate) -> float:
    ac = MetadataNormalizer.comparison_composer(a.composer) if a.composer else ""
    bc = MetadataNormalizer.comparison_composer(b.composer) if b.composer else ""
    return 1.0 if ac and ac == bc else 0.0


def _as_identity(work: object) -> dict[str, object]:
    if isinstance(work, dict):
        identity = work.get("identity")
        if isinstance(identity, dict):
            return identity
    return {}


def _confidence(identity: dict[str, object]) -> float:
    try:
        return float(cast("float", identity.get("confidence") or 0))
    except (TypeError, ValueError):
        return 0.0
