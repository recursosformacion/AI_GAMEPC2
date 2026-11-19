#!/usr/bin/env python
"""Enriquece personas ya mapeadas a Wikidata (`persons_identity.wikidata_qid`).

Resumen: lee de `osap_storage` las personas con QID de Wikidata, consulta Wikidata en
lote (SPARQL `VALUES`) y deja candidatos en `enrichment_candidates` (osap_api). Solo
escribe en la tabla de staging; no modifica `persons`/`works`/índice. Dry-run por defecto.

Uso:
    python script/enrich_identity_batch.py --limit 80
    python script/enrich_identity_batch.py --limit 500 --stage \
        --db-user osap2027 --db-password *** --storage-name osap_storage --stage-name osap_api
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymysql  # noqa: E402
from pymysql.cursors import DictCursor  # noqa: E402

from src.osap.application.enrichment import staging  # noqa: E402
from src.osap.application.enrichment.wikidata import (  # noqa: E402
    WikidataSource,
    looks_like_qid,
    person_candidates,
)

if TYPE_CHECKING:
    from src.osap.application.enrichment.models import EnrichmentCandidate  # noqa: E402

_QUERY = """
SELECT p.persons_id, p.persons_name, p.persons_birth_year, p.persons_death_year,
       p.persons_nationality, p.persons_image_url, MIN(pi.identity_value) AS qid
FROM persons p
JOIN persons_identity pi
  ON pi.persons_id = p.persons_id AND pi.identity_type = 'wikidata_qid'
WHERE p.persons_merged_into IS NULL
GROUP BY p.persons_id, p.persons_name, p.persons_birth_year, p.persons_death_year,
         p.persons_nationality, p.persons_image_url
ORDER BY p.persons_name
LIMIT %s OFFSET %s
"""


def _connect(host: str, port: int, user: str, password: str, database: str) -> Any:
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


def _qid(value: Any) -> str:
    text = str(value or "").strip()
    if "/" in text:
        text = text.rstrip("/").rsplit("/", 1)[-1]
    return text if looks_like_qid(text) else ""


def _blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--chunk", type=int, default=40)
    ap.add_argument("--stage", action="store_true")
    ap.add_argument("--db-host", default="127.0.0.1")
    ap.add_argument("--db-port", type=int, default=3306)
    ap.add_argument("--db-user", required=True)
    ap.add_argument("--db-password", default="")
    ap.add_argument("--storage-name", default="osap_storage")
    ap.add_argument("--stage-name", default="osap_api")
    args = ap.parse_args()

    storage = _connect(args.db_host, args.db_port, args.db_user, args.db_password, args.storage_name)
    try:
        with storage.cursor() as cur:
            cur.execute(_QUERY, (args.limit, args.offset))
            rows = list(cur.fetchall())
    finally:
        storage.close()

    source = WikidataSource()
    candidates: list[EnrichmentCandidate] = []
    processed = 0
    found = 0
    fill_birth = fill_death = fill_image = 0
    ids_fields = 0

    qids = sorted({_qid(r["qid"]) for r in rows if _qid(r["qid"])})
    for start in range(0, len(qids), max(1, args.chunk)):
        batch = qids[start : start + args.chunk]
        results = source.fetch_persons_batch(batch)
        for row in rows:
            qid = _qid(row["qid"])
            data = results.get(qid)
            if not data:
                continue
            processed += 1
            found += 1
            person_id = str(row["persons_id"])
            candidates.extend(person_candidates(qid, data, entity_key=person_id))
            if _blank(row["persons_birth_year"]) and data.get("birth_year") is not None:
                fill_birth += 1
            if _blank(row["persons_death_year"]) and data.get("death_year") is not None:
                fill_death += 1
            if _blank(row["persons_image_url"]) and data.get("image"):
                fill_image += 1
            if data.get("gnd") or data.get("isni") or data.get("viaf"):
                ids_fields += 1

    print(f"personas_leidas={len(rows)} personas_con_datos_wikidata={found}")
    print(f"candidatos={len(candidates)}")
    print(f"podrian_rellenar: nacimiento={fill_birth} fallecimiento={fill_death} imagen={fill_image}")
    print(f"con identificadores (gnd/isni/viaf)={ids_fields}")

    if args.stage:
        conn = staging.connect(args.db_host, args.db_user, args.db_password, args.stage_name, args.db_port)
        try:
            staging.ensure_schema(conn)
            count = staging.stage_candidates(conn, candidates)
        finally:
            conn.close()
        print(f"staged={count} en {args.stage_name}.enrichment_candidates")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
