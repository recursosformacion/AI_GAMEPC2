#!/usr/bin/env python
"""Procesar 250 obras (works250.json, producción) → fichero de resultados + resumen.

Simula el flujo "storage → 250 peticiones": por cada obra identifica la obra (proveedores),
resuelve/valida el compositor y calcula `resolution_confidence`. Escribe cada resultado
incrementalmente (JSONL) y, al final, un resumen estadístico con incidencias.

Uso:
    python script/process_250_batch.py [--limit N] [--out script/works250.processed.jsonl]
    # con OSAP_DEPLOYMENT=prod OSAP_DOTENV=.env.production OSAP_IMSLP_VERIFY_SSL=false
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from src.osap.application.resolution_confidence import classify, resolution_confidence
from src.osap.application.song_search import SongSearch, title_key
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire
from src.osap.infrastructure.identifiers.open_sources import composer_identifiers

_INPUT = Path(__file__).resolve().parent / "works250.json"


def _validate(name: str | None) -> tuple[bool, str | None]:
    if not name:
        return False, None
    rec = composer_identifiers(str(name))
    if rec is not None and (rec.isni or rec.viaf):
        return True, rec.isni or rec.viaf
    return False, None


def _process(work: dict[str, object], searcher: SongSearch) -> dict[str, object]:
    title = str((work.get("work") or {}).get("title") or "")
    hint = (work.get("composer") or {}).get("name") if isinstance(work.get("composer"), dict) else None
    incidents: list[str] = []

    results = searcher.search(title)
    good = [r for r in results if float(r.get("score") or 0) >= 0.5]
    found = bool(good)
    providers = sorted({str(r["provider"]) for r in good})
    source_composers = list(dict.fromkeys(str(r["composer"]) for r in good if r.get("composer")))
    best = good[0] if good else None

    composer_value = hint or (source_composers[0] if source_composers else None)
    validated, id_value = _validate(composer_value)
    if not composer_value:
        incidents.append("sin compositor en input ni en fuentes")
    elif not validated:
        incidents.append(f"compositor no validado en Wikidata ({composer_value})")
    if not found:
        incidents.append("obra no encontrada en proveedores")
    if len(source_composers) > 1:
        incidents.append(f"atribuciones múltiples/conflictivas: {source_composers[:3]}")

    conf = resolution_confidence(
        recovered=found,
        wikidata_work=False,
        provider_count=len(providers),
        composer_found=bool(composer_value),
        composer_from_field=True,
        composer_validated=validated,
    )
    status = classify(conf.total)
    return {
        "id": str(work.get("id") or ""),
        "input": {"title": title, "composer_hint": hint},
        "work_identity": {
            "found": found,
            "title_key": title_key(title),
            "providers": providers,
            "best_match": best.get("title") if best else None,
        },
        "composer": {
            "value": composer_value,
            "source_composers": source_composers,
            "validated": validated,
            "identifier": id_value,
        },
        "resolution_confidence": conf.total,
        "status": status,
        "incidents": incidents,
    }


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "works250.processed.jsonl")
    args = parser.parse_args()

    doc = json.loads(_INPUT.read_text(encoding="utf-8"))
    works = doc if isinstance(doc, list) else doc.get("works", [])
    if args.limit:
        works = works[: args.limit]

    container = wire(Container())
    providers = {p.provider_id.value: p for p in container.catalog_manager().providers()}
    searcher = SongSearch(providers)

    results: list[dict[str, object]] = []
    for work in works:
        try:
            res = _process(work, searcher)
        except Exception as exc:  # noqa: BLE001
            res = {"id": str(work.get("id") or ""), "status": "error", "incidents": [f"excepción: {exc}"]}
        results.append(res)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(res, ensure_ascii=False) + "\n")
        print(f"[{res['id']}] {str(work.get('work',{}).get('title',''))[:30]:32} "
              f"conf={res.get('resolution_confidence', 0):.2f} {res.get('status')}")
        time.sleep(0.5)  # pacing básico

    counts = Counter(str(r.get("status")) for r in results)
    print("\n=== RESUMEN ===")
    for k in ("resolved", "resolved_candidate", "ambiguous", "not_found", "error"):
        print(f"  {k:20} → {counts[k]}")
    incident_counts = Counter(i for r in results for i in r.get("incidents") or [])
    print("\n=== INCIDENCIAS ===")
    for inc, n in incident_counts.most_common():
        print(f"  {n:>3}  {inc}")
    print(f"\nResultados: {args.out} ({len(results)} obras)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
