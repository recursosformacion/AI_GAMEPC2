#!/usr/bin/env python
"""Extraer compositores del dump completo de Wikidata (autoritativo).

Formato del dump: `latest-all.json.bz2` — cada línea es un item JSON independiente.
Este parser hace stream (bz2 → línea) y extrae los items con ocupación compositor
(P106 = Q36834) y sus identificadores (P213 ISNI, P214 VIAF, P244 LCCN, P434 MusicBrainz)
+ label en inglés + aliases.

Escalable: no carga el dump en memoria, solo los compositores que interesan.

Uso:
    python script/extract_composers_from_dump.py --in latest-all.json.bz2 \
        --out data/authority/composers_wikidata.json
"""

from __future__ import annotations

import argparse
import bz2
import json
import sys
from pathlib import Path

COMPOSER_OCCUPATION = "Q36834"
CLAIM = {  # property -> claim mainsnak datavalue key
    "P213": "isni",
    "P214": "viaf",
    "P244": "lccn",
    "P434": "musicbrainz",
}


def _value(claim_datas: list[object]) -> str | None:
    for cd in claim_datas or []:
        if not isinstance(cd, dict):
            continue
        snak = cd.get("mainsnak") or {}
        dv = snak.get("datavalue") or {}
        value = dv.get("value")
        if isinstance(value, dict):
            return value.get("id") or value.get("text")
        if isinstance(value, str):
            return value
    return None


def _is_composer(claims: dict[str, object]) -> bool:
    occupations = claims.get("P106")
    if not isinstance(occupations, list):
        return False
    for occ in occupations:
        if not isinstance(occ, dict):
            continue
        snak = occ.get("mainsnak") or {}
        dv = snak.get("datavalue") or {}
        value = dv.get("value")
        if isinstance(value, dict) and value.get("id") == COMPOSER_OCCUPATION:
            return True
    return False


def extract(dump_path: Path, out_path: Path) -> None:
    open_fn = (bz2.open if dump_path.suffix == ".bz2" else open)
    records: list[dict[str, object]] = []
    n_items = 0
    n_composers = 0
    with open_fn(dump_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            n_items += 1
            if not isinstance(item, dict) or not _is_composer(item.get("claims") or {}):
                continue
            claims = item.get("claims") or {}
            labels = item.get("labels") or {}
            en_label = (labels.get("en") or {}).get("value") if isinstance(labels, dict) else None
            rec: dict[str, object] = {
                "qid": item.get("id"),
                "label": en_label,
                "aliases": [
                    (a or {}).get("value") for a in (item.get("aliases") or {}).get("en", [])
                    if isinstance(a, dict) and a.get("value")
                ][:20],
            }
            for prop, field in CLAIM.items():
                value = _value(claims.get(prop) or [])
                if value:
                    rec[field] = value
            records.append(rec)
            n_composers += 1
            if n_composers % 10000 == 0:
                print(f"{n_composers} compositores (de {n_items} items)", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\nDONE: {n_composers} compositores -> {out_path} ({size_mb:.0f} MB)")


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="dump", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/authority/composers_wikidata.json"))
    args = parser.parse_args()
    if not args.dump.exists():
        print(f"No existe {args.dump}", file=sys.stderr)
        return 2
    extract(args.dump, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
