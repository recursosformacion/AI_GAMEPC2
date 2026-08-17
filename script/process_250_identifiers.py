#!/usr/bin/env python
"""Procesar works250 con enriquecimiento de identificadores (fuentes abiertas).

Para cada obra: compositor → ISNI/VIAF (Wikidata); obra → ISWC (MusicBrainz best-effort)
+ wikidata_work. Archiva por autor y por obra. Resiste rate-limit/errores (skips).

Uso:
    python script/process_250_identifiers.py [--results script/works250.results.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from src.osap.infrastructure.identifiers.archive import IdentifierArchive, WorkRecord
from src.osap.infrastructure.identifiers.open_sources import composer_identifiers, work_iswc, work_wikidata

_DEFAULT_RESULTS = Path(__file__).resolve().parent / "works250.results.json"
_DEFAULT_ARCHIVE = "data/authority"


def _delay() -> None:
    time.sleep(0.25)


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=_DEFAULT_RESULTS)
    parser.add_argument("--archive", type=str, default=_DEFAULT_ARCHIVE)
    parser.add_argument("--limit", type=int, default=None, help="Limita nº de obras procesadas")
    args = parser.parse_args()
    if not args.results.exists():
        print(f"No existe: {args.results}", file=sys.stderr)
        return 2
    doc = json.loads(args.results.read_text(encoding="utf-8"))
    results = doc.get("results") if isinstance(doc.get("results"), list) else []
    if args.limit:
        results = results[: args.limit]

    archive = IdentifierArchive(args.archive)

    # --- compositores únicos → ISNI/VIAF ---
    comp_counter: Counter[str] = Counter()
    for r in results:
        resolved = r.get("resolved") or {}
        comp = resolved.get("composer")
        if isinstance(comp, dict) and comp.get("name"):
            comp_counter[str(comp["name"])] += 1
    found_isni = 0
    for name, n in comp_counter.items():
        try:
            rec = composer_identifiers(name)
        except Exception:  # noqa: BLE001
            rec = None
        if rec is not None:
            archive.upsert_composer(rec)
            if rec.isni:
                found_isni += 1
            print(f"comp {name!r} (x{n}): isni={rec.isni} wikidata={rec.wikidata} viaf={rec.viaf}")
        else:
            print(f"comp {name!r} (x{n}): (no encontrado en Wikidata)")
        _delay()

    # --- obras → ISWC + wikidata_work ---
    found_iswc = 0
    found_work_q = 0
    for i, r in enumerate(results, 1):
        normalized = r.get("normalized") or {}
        title = str(normalized.get("title_raw") or "")
        resolved = r.get("resolved") or {}
        comp = resolved.get("composer")
        composer_name = comp.get("name") if isinstance(comp, dict) else None
        if not title:
            continue
        try:
            iswc = work_iswc(title)
            wq = work_wikidata(title)
        except Exception:  # noqa: BLE001
            iswc, wq = None, None
        if iswc:
            found_iswc += 1
        if wq:
            found_work_q += 1
        archive.upsert_work(
            WorkRecord(
                work_key=title.strip().lower(),
                title=title,
                composer_ref=composer_name,
                iswc=iswc,
                wikidata_work=wq,
                source="open",
            )
        )
        if i % 25 == 0 or iswc or wq:
            print(f"work[{i}/{len(results)}] {title!r}: iswc={iswc} wikidata_work={wq}")
        _delay()

    print("\n=== RESUMEN ===")
    print(f"compositores únicos      : {len(comp_counter)}")
    print(f"compositores con ISNI    : {found_isni}")
    print(f"obras procesadas         : {len(results)}")
    print(f"obras con ISWC (best-effort): {found_iswc}")
    print(f"obras con wikidata_work  : {found_work_q}")
    print(f"archivo: {args.archive}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
