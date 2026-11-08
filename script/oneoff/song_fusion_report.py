#!/usr/bin/env python
"""Reporte de fusión de canciones: primero la seguridad de la CANCIÓN, luego el compositor.

Reusa SongSearch (extracción) + fusión por clave de título. Para cada obra mide:
  - records encontrados (across proveedores)
  - identidades distintas (title_key) -> seguridad de la canción
  - si durante el proceso llega compositor (y desde dónde)

Seguridad de la canción (no fuzzy):
  - 0 records      -> not_found
  - 1 title_key    -> certain (la canción es UNA)
  - >1 title_key   -> ambiguous (la query devuelve varias obras distintas)

Uso:
    python script/song_fusion_report.py
    # con OSAP_DEPLOYMENT=prod OSAP_DOTENV=.env.production OSAP_IMSLP_VERIFY_SSL=false
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from src.osap.application.song_search import SongSearch
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire

_DEFAULT_GT = Path(__file__).resolve().parent / "works250.resolution_gt.json"


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gt", type=Path, default=_DEFAULT_GT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    gt = json.loads(args.gt.read_text(encoding="utf-8")).get("items", {})
    ids = sorted(gt, key=int)[: args.limit] if args.limit else sorted(gt, key=int)

    container = wire(Container())
    providers = {p.provider_id.value: p for p in container.catalog_manager().providers()}
    searcher = SongSearch(providers)
    min_score = 0.5  # solo fusionamos coincidencias de título razonables

    summary: Counter[str] = Counter()
    composer_arrived: Counter[str] = Counter()
    print(f"{'id':>4} {'canción':34} {'regs':>4} {'ident':>5} {'seguridad':9} {'compositor'}")

    for case_id in ids:
        title = str(gt[case_id]["title"])
        all_results = searcher.search(title)
        good = [r for r in all_results if float(r.get("score") or 0) >= min_score]
        keys = Counter(r["key"] for r in good)
        distinct = len(keys)
        total = len(good)
        if total == 0:
            certainty = "not_found"
        elif distinct <= 1:
            certainty = "certain"
        else:
            certainty = "ambiguous"
        summary[certainty] += 1

        composers = {(r["provider"], str(r["composer"])) for r in good if r.get("composer")}
        if composers:
            composer_arrived["yes"] += 1
            comp_str = "; ".join(f"{prov}:{name}" for prov, name in sorted(composers)[:2])
        else:
            composer_arrived["no"] += 1
            comp_str = "—"
        print(f"{case_id:>4} {title[:32]:34} {total:>4} {distinct:>5} {certainty:9} {comp_str}")

    total_n = len(ids)
    print("\n=== SEGURIDAD DE LA CANCIÓN ===")
    for c in ("certain", "ambiguous", "not_found"):
        print(f"  {c:10} → {summary[c]}/{total_n}")
    print("\n=== COMPOSITOR DURANTE LA FUSIÓN ===")
    for c in ("yes", "no"):
        print(f"  {c:10} → {composer_arrived[c]}/{total_n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
