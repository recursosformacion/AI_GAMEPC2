#!/usr/bin/env python
"""Reporte de resolution_confidence sobre los 30 (FASE 5.8).

Por obra computa la confianza continua desde señales del ground truth + validación en
Wikidata (ISNI/VIAF), y muestra la distribución. "Da más confianza": las obras con
compositor encontrado (aunque no validado) reciben confianza parcial, no 0.

Uso: python script/confidence_report.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from src.osap.application.resolution_confidence import classify, resolution_confidence
from src.osap.infrastructure.identifiers.open_sources import composer_identifiers

_DEFAULT_GT = Path(__file__).resolve().parent / "works250.resolution_gt.json"


def _validated(name: str | None) -> bool:
    if not name:
        return False
    rec = composer_identifiers(str(name))
    return rec is not None and bool(rec.isni or rec.viaf)


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gt", type=Path, default=_DEFAULT_GT)
    args = parser.parse_args()

    gt = json.loads(args.gt.read_text(encoding="utf-8")).get("items", {})
    classes: Counter[str] = Counter()
    print(f"{'id':>4} {'canción':30} {'ident':>6} {'atrib':>6} {'valid':>6} {'conf':>6} {'clase':22}")
    for case_id in sorted(gt, key=int):
        it = gt[case_id]
        s = it["signals"]
        title = str(it["title"])
        composer_value = s.get("composer_value")
        validated = _validated(composer_value)
        time.sleep(1.5)
        c = resolution_confidence(
            recovered=bool(s.get("recovered")),
            wikidata_work=bool(s.get("wikidata_work")),
            provider_count=int(s.get("provider_count") or 0),
            composer_found=bool(composer_value),
            composer_from_field=(s.get("composer_source_field") == "composer"),
            composer_validated=validated,
        )
        cls = classify(c.total)
        classes[cls] += 1
        print(f"{case_id:>4} {title[:28]:30} {c.identity:>6.2f} {c.attribution:>6.2f} "
              f"{c.validation:>6.2f} {c.total:>6.2f} {cls:22}")

    n = len(gt)
    print("\n=== DISTRIBUCIÓN ===")
    for k in ("resolved", "resolved_candidate", "ambiguous"):
        print(f"  {k:20} → {classes[k]}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
