#!/usr/bin/env python
"""Enriquecer identificadores de obras/compositores desde fuentes abiertas.

De donde se pueda, sin credenciales:
  * Compositor → ISNI, VIAF, LCCN, MusicBrainz, Wikidata (Wikidata SPARQL).
  * Obra → ISWC best-effort (MusicBrainz), wikidata_work (Wikidata).

Se archiva por obra y por autor en `data/authority/`. Cuando lleguen las credenciales
CISAC (ISWC/IPI) se añadirá esa fuente.

Uso:
    python script/enrich_identifiers.py --composer "Edmund Simon Lorenz"
    python script/enrich_identifiers.py --work "Ave Verum Corpus"
    python script/enrich_identifiers.py --works file.json --archive data/authority
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.osap.infrastructure.identifiers.archive import IdentifierArchive, WorkRecord
from src.osap.infrastructure.identifiers.open_sources import composer_identifiers, work_iswc, work_wikidata

_DEFAULT_ARCHIVE = "data/authority"


def _composer_key(name: str) -> str:
    from src.osap.application.metadata_normalizer import MetadataNormalizer

    return MetadataNormalizer.comparison_composer(name) or name.strip().lower()


def enrich_composer(archive: IdentifierArchive, name: str) -> None:
    rec = composer_identifiers(name)
    if rec is None:
        print(f"composer {name!r}: no encontrado en Wikidata")
        return
    archive.upsert_composer(rec)
    print(
        f"composer {rec.canonical_name!r}: wikidata={rec.wikidata} isni={rec.isni} "
        f"viaf={rec.viaf} lccn={rec.lccn} mb={rec.musicbrainz} aliases={rec.aliases[:3]}"
    )


def enrich_work(archive: IdentifierArchive, title: str, composer: str | None = None) -> None:
    iswc = work_iswc(title)
    wqid = work_wikidata(title)
    key = _composer_key(composer) if composer else None
    rec = WorkRecord(
        work_key=title.strip().lower(),
        title=title,
        composer_ref=key,
        iswc=iswc,
        wikidata_work=wqid,
        musicbrainz_work=iswc,
        source="open",
    )
    archive.upsert_work(rec)
    print(f"work {title!r}: iswc={iswc} wikidata_work={wqid}")


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--composer", type=str, default=None)
    parser.add_argument("--work", type=str, default=None)
    parser.add_argument("--works", type=Path, default=None, help="JSON: [{'title','composer'}]")
    parser.add_argument("--archive", type=str, default=_DEFAULT_ARCHIVE)
    args = parser.parse_args()

    archive = IdentifierArchive(args.archive)
    if args.composer:
        enrich_composer(archive, args.composer)
    if args.work:
        enrich_work(archive, args.work)
    if args.works:
        data = json.loads(args.works.read_text(encoding="utf-8"))
        entries = data if isinstance(data, list) else data.get("works", [])
        for e in entries:
            if not isinstance(e, dict):
                continue
            if e.get("composer"):
                enrich_composer(archive, str(e["composer"]))
            if e.get("title"):
                enrich_work(archive, str(e["title"]), e.get("composer"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
