#!/usr/bin/env python
"""FASE 5.7.1 — re-evaluar los 30 etiquetados con el matcher nuevo (reconstrucción por obra).

Produce ANTES/DESPUÉS/Δ de error_class y, por obra, el estado de recuperación:
    input → OMR raw → matcher → grouping → obra → compositor → resolución

Distingue candidate_missing real (OMR la tiene pero el matcher la pierde) de obra
recuperada con compositor desconocido. Requiere acceso a producción (token storage:read).

Uso:
    python script/reeval_30.py [--results script/works250.results.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import ProviderQuery
from src.osap.infrastructure.resolution.universe_matching import SimpleUniverseMatcher

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resolution_eval  # noqa: E402
import trace_candidate_missing  # noqa: E402

_DEFAULT_RESULTS = Path(__file__).resolve().parent / "works250.results.json"
_DEFAULT_SAMPLE = Path(__file__).resolve().parent / "works250.sample.json"


def _universe_from_omr(title: str, fetcher) -> list[dict[str, object]]:
    data = fetcher.fetch(None, None, ProviderQuery(query=title, title=title))
    works = data.get("works") if isinstance(data, dict) else []
    universe: list[dict[str, object]] = []
    for w in works:
        if not isinstance(w, dict):
            continue
        universe.append(
            {"provider": "omr", "work": {"identity": {
                "id": w.get("id"), "title": w.get("title"),
                "composer": w.get("composer"), "catalogue": w.get("catalogue"), "confidence": 0.9,
            }}}
        )
    return universe


def _matching_item(items: list[dict[str, object]], title: str) -> dict[str, object] | None:
    # Caso-insensitive (title_raw) + clave normalizada (tolerante a ruido de título).
    key = MetadataNormalizer.normalize_title_with_trace(title).key
    low = title.strip().lower()
    for it in items:
        raw = str(it.get("normalized", {}).get("title_raw") or "").strip()
        if raw.lower() == low:
            return it
        if str(it.get("normalized", {}).get("title") or "") == key:
            return it
    return None


def _after_class(raw_count: int, item_found: bool, item_status: str | None) -> str:
    if raw_count == 0:
        return "not_found"
    if not item_found:
        return "candidate_missing"
    if item_status == "resolved":
        return "correct"
    return "ambiguous"  # obra recuperada, compositor desconocido


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=_DEFAULT_RESULTS)
    parser.add_argument("--sample", type=Path, default=_DEFAULT_SAMPLE)
    args = parser.parse_args()

    results_doc = json.loads(args.results.read_text(encoding="utf-8"))
    results = results_doc.get("results") if isinstance(results_doc.get("results"), list) else []
    results_by_id = {str(r.get("id")): r for r in results}

    sample = json.loads(args.sample.read_text(encoding="utf-8")).get("items", {})
    fetcher = trace_candidate_missing._tokenized_fetcher()
    matcher = SimpleUniverseMatcher()

    before: Counter[str] = Counter()
    after: Counter[str] = Counter()
    print(f"{'id':>6} {'título':30} {'raw':>3} {'matcher':>7} {'status':>9}  ANTES→DESPUÉS")
    for case_id, entry in sample.items():
        label = str(entry.get("label") or "unknown")
        cc = str(entry.get("correct_candidate") or "")
        title = str(entry.get("note") or "")
        result = results_by_id.get(case_id)
        before_cls = resolution_eval.auto_error_class(result, label, cc) if result else "?"

        raw = _universe_from_omr(title, fetcher)
        items = matcher.match(raw)
        item = _matching_item(items, title)
        raw_count = len(raw)
        item_found = item is not None
        item_status = item.get("status") if item else None
        after_cls = _after_class(raw_count, item_found, item_status)

        before[before_cls or "unknown"] += 1
        after[after_cls] += 1
        print(f"{case_id:>6} {title[:28]:30} {raw_count:>3} {str(item_found):>7} "
              f"{str(item_status):>9}  {before_cls or '?':9}→{after_cls}")

    keys = ["candidate_missing", "wrong_rank", "candidate_correct_but_insufficient_evidence",
            "genuine_ambiguity", "genuine_not_found", "correct"]
    print("\n" + f"{'clase':40} {'ANTES':>6} {'DESPUÉS':>7} {'Δ':>4}")
    for k in keys:
        b = before.get(k, 0)
        a = after.get(k, 0)
        print(f"{k:40} {b:>6} {a:>7} {a - b:>+4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
