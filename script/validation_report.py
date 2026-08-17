#!/usr/bin/env python
"""Validación de compositor → `resolved` seguro (FASE 5.8).

`resolved` requiere:
  1. canción recuperada (identidad de obra cierta),
  2. se encontró compositor durante la fusión,
  3. el compositor SE VALIDA contra una BDD libre de compositores (Wikidata ISNI/VIAF).

Solo si se valida → `resolved`. Sin validación → `ambiguous` (inseguro).
Uso: python script/validation_report.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from src.osap.infrastructure.identifiers.open_sources import composer_identifiers
from src.osap.infrastructure.resolvers.wikidata_work_attributor import WikidataWorkAttributor

_DEFAULT_GT = Path(__file__).resolve().parent / "works250.resolution_gt.json"


def _validate(name: str | None) -> bool:
    if not name:
        return False
    rec = composer_identifiers(str(name))
    return rec is not None and bool(rec.isni or rec.viaf)


def _wikidata_work_composer(title: str, attributor: WikidataWorkAttributor) -> str | None:
    """Si la consulta de la OBRA en Wikidata dio compositor, devolver su nombre/código."""
    results = attributor.attribute(title)
    for c in results:
        if not isinstance(c, dict):
            continue
        return str(c.get("name") or c.get("composer_qid") or "")
    return None


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gt", type=Path, default=_DEFAULT_GT)
    args = parser.parse_args()

    gt = json.loads(args.gt.read_text(encoding="utf-8")).get("items", {})
    counts = {"resolved": 0, "ambiguous": 0, "not_found": 0}
    attributor = WikidataWorkAttributor()
    print(f"{'id':>4} {'canción':34} {'rec':>3} {'comp':>4} {'validado':8} {'decisión'}")
    for case_id in sorted(gt, key=int):
        it = gt[case_id]
        s = it["signals"]
        title = str(it["title"])
        recovered = bool(s.get("recovered"))
        composer_value = s.get("composer_value")
        wd_composer = _wikidata_work_composer(title, attributor)  # obra→compositor (Wikidata)
        validated = _validate(wd_composer or composer_value)
        time.sleep(1.5)  # pacing: Wikidata rate-limit en bulto
        if not recovered:
            decision = "not_found"
        elif (wd_composer or composer_value) and validated:
            decision = "resolved"
        else:
            decision = "ambiguous"
        counts[decision] += 1
        print(f"{case_id:>4} {title[:32]:34} {str(recovered):>3} {str(bool(composer_value or wd_composer)):>4} "
              f"{str(validated):>8} {decision}")

    n = len(gt)
    print("\n=== RESOLVED SEGURO (con validación) ===")
    for k in ("resolved", "ambiguous", "not_found"):
        print(f"  {k:9} → {counts[k]}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
