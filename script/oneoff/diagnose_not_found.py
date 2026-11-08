#!/usr/bin/env python
"""Diagnóstico de los not_found de la autoridad local sobre las 100 primeras obras.

Para cada obra consulta el pipeline (OMR/IMSLP/RISM/MusicBrainz) y clasifica qué aporta:
  * resoluble_por_identificador : alguna fuente da el compositor CON id (viaf/mbid/qid)
  * resoluble_por_nombre        : alguna fuente da el compositor (sin id fuerte)
  * ambiguo                     : varias fuentes / compositores en conflicto
  * desconocido                 : ninguna fuente aporta el compositor

Solo lectura. Requiere la API/proveedores (OSAP_DEPLOYMENT=prod + .env.production).

Uso:
    python script/diagnose_not_found.py [--limit 100] [--from-id 0]
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

_INPUT = Path(__file__).resolve().parent / "works250.json"


def composer_key_raw(raw: str) -> str:
    # self-contained (no depender del normalizer en runtime si cambia)
    import re

    text = re.sub(r"\([^)]*\)", "", (raw or "").strip().lower())
    tokens = [t for t in text.split() if t]
    if not tokens:
        return ""
    last = tokens[-1]
    firsts = "".join(t[0] for t in tokens[:-1] if t[0].isalnum())
    return f"{firsts} {last}".strip()


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--from-id", type=int, default=0)
    parser.add_argument("--works", type=Path, default=None, help="JSON: [{'id','title','composer'}] (alternativa)")
    args = parser.parse_args()

    works: list[dict] = []
    if args.works:
        works = json.loads(args.works.read_text(encoding="utf-8"))
    else:
        # Leer de la BD de osap-storage (producción usa BD, no JSONL).
        import pymysql

        conn = pymysql.connect(host="127.0.0.1", user="osap2027", password="2027osapdb", database="osap-storage")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, composer FROM works WHERE id > %s ORDER BY id LIMIT %s",
                    (args.from_id, args.limit),
                )
                works = [{"id": r[0], "title": r[1], "composer": r[2]} for r in cur.fetchall()]
        finally:
            conn.close()

    container = wire(Container())
    providers = {p.provider_id.value: p for p in container.catalog_manager().providers()}
    searcher = SongSearch(providers)

    stats: Counter = Counter()
    examples: dict[str, list[str]] = {"resoluble_por_identificador": [], "resoluble_por_nombre": [],
                                      "ambiguo": [], "desconocido": []}
    detail: list[str] = []
    for w in works:
        wid = int(w["id"])
        title = w["title"] or ""
        hint = (w["composer"] or "").strip()
        if not hint:
            stats["sin_compositor"] += 1
            continue
        results = searcher.search(title)
        # candidatos que coinciden con el compositor hint (normalizado)
        key = composer_key_raw(hint)
        matched = []
        strong = []
        for r in results:
            comp = r.get("composer")
            if not comp:
                continue
            if composer_key_raw(str(comp)) == key:
                ids = r.get("external_ids") or {}
                strong_ids = {k: v for k, v in ids.items() if k in ("viaf", "musicbrainz", "mbid", "qid", "isni")}
                matched.append(str(comp))
                if strong_ids:
                    strong.append((str(comp), strong_ids))
        if strong:
            stats["resoluble_por_identificador"] += 1
            examples["resoluble_por_identificador"].append(f"{hint}->{strong[0]}")
            detail.append(f"[{wid}] {hint:24} -> IDENTIFICADOR {strong[0]}")
        elif matched:
            stats["resoluble_por_nombre"] += 1
            examples["resoluble_por_nombre"].append(f"{hint}->{matched[0]}")
            detail.append(f"[{wid}] {hint:24} -> NOMBRE {matched[0]}")
        elif len(results) > 1:
            stats["ambiguo"] += 1
            detail.append(f"[{wid}] {hint:24} -> AMBIGUO")
        else:
            stats["desconocido"] += 1
            detail.append(f"[{wid}] {hint:24} -> DESCONOCIDO")
        print(f"[{wid}] {hint or '-'}", flush=True)

    print(f"=== DIAGNÓSTICO ({len(works)} obras) ===")
    for k in ("resoluble_por_identificador", "resoluble_por_nombre", "ambiguo", "desconocido", "sin_compositor"):
        print(f"  {k:26}: {stats[k]}")
    print("\nEJEMPLOS:")
    for k, items in examples.items():
        if items:
            print(f"  {k}: {items[:4]}")
    print("\nDETALLE (primeros 30):")
    for d in detail[:30]:
        print("  " + d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
