#!/usr/bin/env python
"""Fusionar fuentes de compositores en un único índice (`composers_index.json`).

Cada fuente aporta una lista de compositores con IDs (Wikidata: qid/isni/viaf/lccn/mb;
futuras: IMSLP name, VIAF id...). Se normaliza el nombre y se agrupa por clave canónica:
    { clave_canónica: [ {source, name, isni, viaf, ...}, ... ] }

Así la validación de los 250 consulta un solo índice local (sin red ni rate-limit).

Uso:
    python script/build_composers_index.py \
        --src wikidata=data/authority/composers_wikidata.json \
        [--src imslp=.../imslp_composers.json] [--out data/authority/composers_index.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from src.osap.application.metadata_normalizer import MetadataNormalizer


def _load(path: Path, source: str) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data if isinstance(data, list) else data.get("records", [])
    rows: list[dict[str, object]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        name = rec.get("label") or rec.get("name")
        if not name:
            continue
        key = MetadataNormalizer.comparison_composer(str(name))
        if not key:
            continue
        rows.append(
            {
                "source": source,
                "key": key,
                "name": str(name),
                "qid": rec.get("qid"),
                "isni": rec.get("isni"),
                "viaf": rec.get("viaf"),
                "lccn": rec.get("lccn"),
                "musicbrainz": rec.get("musicbrainz"),
                "mbid": rec.get("mbid"),
            }
        )
    return rows


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", action="append", default=[], help="fuente=fichero (repetible)")
    parser.add_argument("--out", type=Path, default=Path("data/authority/composers_index.json"))
    args = parser.parse_args()
    if not args.src:
        print("Indica al menos --src fuente=fichero", file=sys.stderr)
        return 2

    index: dict[str, list[dict[str, object]]] = defaultdict(list)
    for spec in args.src:
        source, _, raw_path = spec.partition("=")
        path = Path(raw_path)
        if not path.exists():
            print(f"(skip) no existe {path}", file=sys.stderr)
            continue
        rows = _load(path, source)
        for row in rows:
            index[str(row["key"])].append(row)
        print(f"{source}: {len(rows)} compositores ({path})")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dict(index), ensure_ascii=False), encoding="utf-8")
    size_mb = args.out.stat().st_size / 1024 / 1024
    print(f"\nÍNDICE UNIFICADO: {len(index)} claves -> {args.out} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
