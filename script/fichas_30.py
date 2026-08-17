#!/usr/bin/env python
"""Fichas de ground truth de los 30: evidencia + procedencia + candidatos + conflictos.

Combina el ground truth (evidence_trace) con los candidatos originales de
works250.results.json, y propone una etiqueta (resolved/ambiguous/not_found) que el
humano corrige. La propuesta es una pista: resolved solo si hay atribución explícita de
fuente y no hay conflicto evidente de candidatos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_DEFAULT_RESULTS = Path(__file__).resolve().parent / "works250.results.json"
_DEFAULT_GT = Path(__file__).resolve().parent / "works250.resolution_gt.json"


def _candidates_summary(result: dict[str, object] | None) -> tuple[str, list[str]]:
    if not result:
        return "?", []
    resolved = result.get("resolved") or {}
    comp = resolved.get("composer")
    decided = comp.get("name") if isinstance(comp, dict) else None
    names = []
    for c in result.get("candidates") or []:
        if isinstance(c, dict) and c.get("name"):
            names.append(str(c["name"]))
    return decided or "?", names


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=_DEFAULT_RESULTS)
    parser.add_argument("--gt", type=Path, default=_DEFAULT_GT)
    args = parser.parse_args()

    rd = json.loads(args.results.read_text(encoding="utf-8"))
    results = {str(r.get("id")): r for r in (rd.get("results") or [])}
    gt = json.loads(args.gt.read_text(encoding="utf-8")).get("items", {})

    for case_id in sorted(gt, key=int):
        it = gt[case_id]
        s = it["signals"]
        ev = it.get("evidence_trace", {})
        cev = ev.get("composer_evidence")
        decided, cands = _candidates_summary(results.get(case_id))
        print("=" * 72)
        print(f"ID {case_id} — {it['title']}")
        print(f"  EVIDENCIA: {ev['omr_records']}")
        print(f"  PROCEDENCIA: {json.dumps(cev, ensure_ascii=False)}")
        print(f"  CANDIDATOS (original): {cands[:8]}{'...' if len(cands) > 8 else ''}  (decidido original: {decided})")
        print(f"  provider_count={s['provider_count']} candidate_count={s['candidate_count']}")
        print(f"  PROPUESTA: {it['suggested_resolution']} ({it['suggestion_reason']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
