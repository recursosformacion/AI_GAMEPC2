#!/usr/bin/env python
"""FASE 5.8 — Ground truth de resolución de los 30 (sin cambiar el algoritmo).

Reprocesa los 30 con el matcher definitivo (recuperación a 0) y, para cada obra, registra
las señales de resolución y propone `expected_resolution` (resolved / resolved_auth /
ambiguous / not_found) para etiquetar manualmente.

Per ADR-0034, una obra recuperada con compositor tradicional/desconocido NO es ambiguous
por falta de compositor: la identidad de la obra está resuelta → `resolved`. El humano
confirma la etiqueta.

Uso:
    python script/ground_truth_30.py [--sample script/works250.sample.json] [--out script/works250.resolution_gt.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import ProviderQuery
from src.osap.infrastructure.resolution.universe_matching import SimpleUniverseMatcher

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trace_candidate_missing  # noqa: E402

_DEFAULT_SAMPLE = Path(__file__).resolve().parent / "works250.sample.json"
_DEFAULT_OUT = Path(__file__).resolve().parent / "works250.resolution_gt.json"


def _universe_from_omr(title: str, fetcher) -> list[dict[str, object]]:
    data = fetcher.fetch(None, None, ProviderQuery(query=title, title=title))
    works = data.get("works") if isinstance(data, dict) else []
    return [
        {"provider": "omr", "work": {"identity": {
            "id": w.get("id"), "title": w.get("title"),
            "composer": w.get("composer"), "catalogue": w.get("catalogue"), "confidence": 0.9,
        }}}
        for w in works if isinstance(w, dict)
    ]


def _matching_item(items: list[dict[str, object]], title: str) -> dict[str, object] | None:
    key = MetadataNormalizer.normalize_title_with_trace(title).key
    low = title.strip().lower()
    for it in items:
        raw = str(it.get("normalized", {}).get("title_raw") or "").strip()
        if raw.lower() == low:
            return it
        if str(it.get("normalized", {}).get("title") or "") == key:
            return it
    return None


def _suggest(omr_composer: str | None, item: dict[str, object] | None, raw_count: int) -> tuple[str, str]:
    """Devuelve (sugerencia, motivo). Es una pista automática, NO ground truth."""
    if raw_count == 0:
        return "not_found", "no_omr_records"
    if item is None:
        return "not_found", "work_not_recovered"
    if omr_composer and str(omr_composer).strip():
        # Evidencia de atribución explícita de fuente; NO decide resolved por sí misma.
        return "ambiguous", "explicit_composer_from_omr"
    return "ambiguous", "no_composer_unknown"


_TRADITIONAL_MARKERS = {
    "anon", "anonymous", "trad", "traditional", "traditionnel", "volksweise",
    "attrib.", "attributed", "attrib", "attr.",
}


def _is_traditional_marker(value: str | None) -> bool:
    # Solo true si la FUENTE lo identifica explícitamente como tradicional/anónimo.
    if not value:
        return False
    return str(value).strip().lower() in _TRADITIONAL_MARKERS


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=_DEFAULT_SAMPLE)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    sample = json.loads(args.sample.read_text(encoding="utf-8")).get("items", {})
    fetcher = trace_candidate_missing._tokenized_fetcher()
    matcher = SimpleUniverseMatcher()

    items_out: dict[str, dict[str, object]] = {}
    for case_id, entry in sample.items():
        title = str(entry.get("note") or "")
        universe = _universe_from_omr(title, fetcher)
        omr_composer = next(
            (
                str(u["work"]["identity"].get("composer") or "").strip() or None
                for u in universe if u["work"]["identity"].get("composer")
            ),
            None,
        )
        items = matcher.match(universe)
        item = _matching_item(items, title)
        composer = None
        composer_evidence = None
        if item is not None:
            c = (item.get("resolved") or {}).get("composer")
            composer = c.get("name") if c else None
            composer_evidence = item.get("composer_evidence")
        cev = composer_evidence if isinstance(composer_evidence, dict) else None
        composer_value = str(cev.get("raw_value")) if cev and cev.get("raw_value") else None
        providers = sorted({u["provider"] for u in universe})
        suggestion, reason = _suggest(omr_composer, item, len(universe))
        evidence_trace = {
            "input_title": title,
            "title_key": MetadataNormalizer.normalize_title_with_trace(title).key,
            "omr_records": [
                {"id": u["work"]["identity"].get("id"), "title": u["work"]["identity"].get("title"),
                 "composer": u["work"]["identity"].get("composer")}
                for u in universe
            ],
            "composer_evidence": composer_evidence,
        }
        field = (cev or {}).get("field")
        signals: dict[str, object] = {
            "omr_records": len(universe),
            "recovered": item is not None,
            "item_status": item.get("status") if item else None,
            "composer": composer,  # normalizado
            "composer_explicit": cev is not None,
            "composer_value": composer_value,  # valor crudo (antes de normalizar)
            "composer_source": (cev or {}).get("source"),
            "composer_source_field": field,
            "composer_from_title": field == "title",
            "composer_from_provider": field == "composer",
            "composer_inferred": bool((cev or {}).get("inferred")),
            "composer_normalization": "comparison_composer" if cev and cev.get("raw_value") else None,
            "composer_traditional": _is_traditional_marker(composer_value),
            "provider_count": len(providers),
            "providers": providers,
            "candidate_count": len(items),
            "title_key": MetadataNormalizer.normalize_title_with_trace(title).key,
            "wikidata_work": None,
            "authority_identifiers": {},
        }
        items_out[str(case_id)] = {
            "title": title,
            "signals": signals,
            "evidence_trace": evidence_trace,
            "expected_resolution": None,  # ground truth HUMANO (null hasta etiquetar)
            "suggested_resolution": suggestion,
            "suggestion_reason": reason,
            "label_note": "",
        }

    args.out.write_text(json.dumps(
        {"schema": "FASE 5.8 ground truth. expected_resolution: resolved|resolved_auth|ambiguous|not_found "
         "(HUMANO, null hasta etiquetar). suggested_resolution: pista automática. "
         "label_note: justificación humana.", "items": items_out},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Ground truth escrito: {args.out}")
    for case_id, it in items_out.items():
        s = it["signals"]
        print(
            f"  [{case_id}] {it['title'][:30]:30} rec={s['recovered']} expl={s['composer_explicit']} "
            f"comp={s['composer_value']!r} → sug={it['suggested_resolution']} ({it['suggestion_reason']})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
