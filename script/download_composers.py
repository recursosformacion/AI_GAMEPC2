#!/usr/bin/env python
"""Descargar fichero de compositores desde Wikidata (SPARQL).

Exporta todos los compositores (P106=Q36834) con Q-id, label y identificadores
(ISNI, VIAF, LCCN, MusicBrainz) a un fichero JSON local, para usar como tabla de
autoridades/validación sin golpear Wikidata en cada resolución.

Paginado por OFFSET (robusto ante timeouts). Con `--limit` se acota el lote de prueba.

Uso:
    python script/download_composers.py [--out data/authority/composers_wikidata.json] [--limit 20000]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

_SPARQL = "https://query.wikidata.org/sparql"
_UA = "osap-download-composers/0.1 (reconstruction; read-only)"
_BATCH = 5000
_MAX_RETRIES = 5


def _query(batch: int, offset: int) -> str:
    return f"""
SELECT ?item ?itemLabel ?isni ?viaf ?lccn ?mbid WHERE {{
  ?item wdt:P106 wd:Q36834 .
  ?item rdfs:label ?label . FILTER(LANG(?label) = 'en')
  OPTIONAL {{ ?item wdt:P213 ?isni }}
  OPTIONAL {{ ?item wdt:P214 ?viaf }}
  OPTIONAL {{ ?item wdt:P244 ?lccn }}
  OPTIONAL {{ ?item wdt:P434 ?mbid }}
}}
LIMIT {batch} OFFSET {offset}
"""


def _fetch(batch: int, offset: int) -> list[dict[str, object]]:
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.get(
                _SPARQL,
                params={"query": _query(batch, offset), "format": "json"},
                headers={"User-Agent": _UA},
                timeout=180,
            )
            if resp.status_code == 429 or resp.status_code >= 500 or "results" not in resp.text:
                raise requests.RequestException(f"status={resp.status_code}")
            data = resp.json()
            bindings = data.get("results", {}).get("bindings", [])
        except Exception as exc:  # noqa: BLE001
            wait = 15 * (attempt + 1)
            print(f"  retry {attempt + 1}/{_MAX_RETRIES} offset={offset}: {exc} (espera {wait}s)", flush=True)
            time.sleep(wait)
            continue
        break
    else:
        return []

    def val(row: dict[str, object], key: str) -> str | None:
        value = row.get(key)
        return value.get("value") if isinstance(value, dict) else None

    rows: list[dict[str, object]] = []
    for row in bindings:
        qid = val(row, "item") or ""
        if qid.startswith("http"):
            qid = qid.rsplit("/", 1)[-1]
        rows.append(
            {
                "qid": qid,
                "label": val(row, "itemLabel"),
                "isni": val(row, "isni"),
                "viaf": val(row, "viaf"),
                "lccn": val(row, "lccn"),
                "musicbrainz": val(row, "mbid"),
            }
        )
    return rows


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/authority/composers_wikidata.json"))
    parser.add_argument("--limit", type=int, default=None, help="Acotar el nº de compositores (prueba)")
    args = parser.parse_args()

    all_rows: list[dict[str, object]] = []
    offset = 0
    while True:
        rows = _fetch(_BATCH, offset)
        all_rows.extend(rows)
        offset += _BATCH
        print(f"offset {offset}: {len(all_rows)} compositores")
        if args.limit and len(all_rows) >= args.limit:
            all_rows = all_rows[: args.limit]
            break
        if len(rows) < _BATCH:
            break
        time.sleep(2)  # pacing: respetar rate-limit de Wikidata

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(all_rows, ensure_ascii=False, indent=1), encoding="utf-8")
    size_mb = args.out.stat().st_size / 1024 / 1024
    print(f"\nGuardado: {args.out} ({len(all_rows)} compositores, {size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
