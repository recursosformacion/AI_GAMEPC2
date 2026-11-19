#!/usr/bin/env python
"""Enriquece una persona u obra desde Wikidata y, opcionalmente, enlaza un IIIF.

Resumen: resuelve una persona/obra (por QID o por nombre/título) en Wikidata, extrae
campos fiables con evidencia y los deja como candidatos. Con `--stage` los guarda en la
tabla de staging `enrichment_candidates` (no toca works/persons/índice). Con
`--iiif-manifest URL` valida un manifiesto IIIF y lo registra como fuente de la obra.

Uso:
    python script/enrich_entity.py --person-qid Q254
    python script/enrich_entity.py --person-name "Wolfgang Amadeus Mozart" --json
    python script/enrich_entity.py --work-title "Eine kleine Nachtmusik" --first
    python script/enrich_entity.py --work-qid Q123456 \
        --iiif-manifest https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb00000001/manifest \
        --stage --db-user osap2027 --db-password *** --db-name osap_api
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.osap.application.enrichment import iiif, staging  # noqa: E402
from src.osap.application.enrichment.wikidata import (  # noqa: E402
    WikidataSource,
    extract_person,
    extract_work,
    looks_like_qid,
    person_candidates,
    work_candidates,
)

if TYPE_CHECKING:
    from src.osap.application.enrichment.models import EnrichmentCandidate  # noqa: E402


def _resolve(source: WikidataSource, text: str, kind: str, first: bool) -> str | None:
    results = source.search(text, kind)
    if not results:
        print(f"Sin resultados en Wikidata para {kind}: {text!r}", file=sys.stderr)
        return None
    if len(results) == 1 or first:
        chosen = results[0]
        print(
            f"Resuelto {kind} {text!r} -> {chosen['qid']} ({chosen['label']})",
            file=sys.stderr,
        )
        return chosen["qid"]
    print(f"Varios candidatos para {kind} {text!r}; usa --{kind}-qid:", file=sys.stderr)
    for item in results:
        print(f"  {item['qid']}  {item['label']}  —  {item['description']}", file=sys.stderr)
    return None


def _print_candidates(candidates: list[EnrichmentCandidate], as_json: bool) -> None:
    if as_json:
        payload = [
            {
                "entity_type": c.entity_type,
                "entity_key": c.entity_key,
                "field": c.field,
                "value": c.value,
                "source": c.source,
                "evidence_url": c.evidence_url,
                "confidence": c.confidence,
                "license": c.license,
            }
            for c in candidates
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for c in candidates:
        print(
            f"{c.entity_type}:{c.entity_key}  {c.field} = {c.value}"
            f"  [{c.source} {c.confidence:.2f}] {c.evidence_url}"
        )
    print(f"-- {len(candidates)} candidatos", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--person-qid")
    group.add_argument("--person-name")
    group.add_argument("--work-qid")
    group.add_argument("--work-title")
    ap.add_argument("--composer", default="", help="filtro orientativo para búsqueda de obra")
    ap.add_argument("--first", action="store_true", help="usa el primer resultado de búsqueda")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--iiif-manifest", default="")
    ap.add_argument("--stage", action="store_true")
    ap.add_argument("--db-host", default=os.environ.get("OSAP_DB_HOST", "127.0.0.1"))
    ap.add_argument("--db-port", type=int, default=int(os.environ.get("OSAP_DB_PORT", "3306")))
    ap.add_argument("--db-user", default=os.environ.get("OSAP_DB_USER", ""))
    ap.add_argument("--db-password", default=os.environ.get("OSAP_DB_PASSWORD", ""))
    ap.add_argument("--db-name", default=os.environ.get("OSAP_DB_NAME", "osap_api"))
    args = ap.parse_args()

    source = WikidataSource()
    candidates: list[EnrichmentCandidate] = []
    work_key = ""

    if args.person_qid or args.person_name:
        qid = args.person_qid or _resolve(source, args.person_name, "person", args.first)
        if not qid:
            return 2
        if not looks_like_qid(qid):
            print(f"QID inválido: {qid}", file=sys.stderr)
            return 2
        candidates = person_candidates(qid, extract_person(source.entity(qid), qid))
    else:
        qid = args.work_qid or _resolve(source, args.work_title, "work", args.first)
        if not qid:
            return 2
        if not looks_like_qid(qid):
            print(f"QID inválido: {qid}", file=sys.stderr)
            return 2
        work_key = qid
        candidates = work_candidates(qid, extract_work(source.entity(qid), qid))

    if args.iiif_manifest:
        if not work_key:
            print("--iiif-manifest requiere una obra (--work-qid/--work-title)", file=sys.stderr)
            return 2
        try:
            payload = iiif.fetch_manifest(iiif.default_session(), args.iiif_manifest)
        except Exception as exc:  # noqa: BLE001
            print(f"No se pudo leer el manifiesto IIIF: {exc}", file=sys.stderr)
            payload = None
        if payload is not None:
            candidates.append(iiif.manifest_candidate(work_key, args.iiif_manifest, payload))

    _print_candidates(candidates, args.json)

    if args.stage:
        if not args.db_user:
            print("Falta --db-user (o OSAP_DB_USER) para --stage", file=sys.stderr)
            return 2
        conn = staging.connect(
            args.db_host, args.db_user, args.db_password, args.db_name, args.db_port
        )
        try:
            staging.ensure_schema(conn)
            count = staging.stage_candidates(conn, candidates)
        finally:
            conn.close()
        print(f"staged: {count} candidatos en {args.db_name}.enrichment_candidates", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
