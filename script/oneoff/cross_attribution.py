#!/usr/bin/env python
"""FASE 5.8 — atribución cruzada reusando la capa de proveedores existente.

En vez de consultas ad hoc, usa los `RemoteCatalogProvider` del container
(catalog_manager().providers()) vía `provider.search(SearchRequest)`, igual que la app.
Wikidata se consulta con el atribuidor de obra→compositor (no es un catalog provider).

Mide la resolución acumulada: OMR → +IMSLP → +Wikidata → +MusicBrainz → +autoridad persona.
Pregunta: ¿problema de algoritmo o de disponibilidad de datos?

Uso:
    python script/cross_attribution.py [--gt script/works250.resolution_gt.json]
    # con OSAP_DEPLOYMENT=prod OSAP_DOTENV=.env.production OSAP_IMSLP_VERIFY_SSL=false
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.osap.api.contracts import SearchRequest
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire
from src.osap.infrastructure.identifiers.open_sources import composer_identifiers
from src.osap.infrastructure.resolvers.wikidata_work_attributor import WikidataWorkAttributor

_DEFAULT_GT = Path(__file__).resolve().parent / "works250.resolution_gt.json"


def _composers_from(provider: object, title: str) -> list[str]:
    if provider is None:
        return []
    try:
        candidates = provider.search(SearchRequest(query=title, title=title, limit=10))  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return []
    out: list[str] = []
    for cand in candidates:
        descriptor = getattr(cand, "work_descriptor", None)
        composer = getattr(descriptor, "composer", None) if descriptor is not None else None
        if composer:
            out.append(str(composer))
    return out


def _wikidata_composers(title: str, attributor: WikidataWorkAttributor) -> list[str]:
    res = attributor.attribute(title)
    return [str(c.get("name") or c.get("composer_qid")) for c in res if isinstance(c, dict)]


def _confirmed_by_authority(names: list[str]) -> bool:
    for name in names:
        rec = composer_identifiers(name)
        if rec is not None and (rec.isni or rec.viaf):
            return True
    return False


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
    attributor = WikidataWorkAttributor()

    rows: dict[str, dict[str, object]] = {}
    for case_id in ids:
        title = str(gt[case_id]["title"])
        omr = _composers_from(providers.get("omr"), title)
        imslp = _composers_from(providers.get("imslp"), title)
        rism = _composers_from(providers.get("rism"), title)
        mb = _composers_from(providers.get("musicbrainz"), title)
        wd = _wikidata_composers(title, attributor)
        all_names = list(dict.fromkeys(omr + imslp + rism + wd + mb))
        confirmed = _confirmed_by_authority(all_names)
        rows[case_id] = {
            "title": title,
            "omr": omr, "imslp": imslp, "rism": rism, "wikidata": wd, "musicbrainz": mb,
            "any_composer": bool(all_names),
            "confirmed_by_authority": confirmed,
        }
        print(f"[{case_id}] {title[:30]:30} OMR={len(omr)} IMSLP={len(imslp)} RISM={len(rism)} "
              f"WD={len(wd)} MB={len(mb)} confirmado={confirmed}")

    levels = {
        "OMR": lambda r: bool(r["omr"]),
        "OMR+IMSLP": lambda r: bool(r["omr"] or r["imslp"]),
        "OMR+IMSLP+RISM": lambda r: bool(r["omr"] or r["imslp"] or r["rism"]),
        "+Wikidata": lambda r: bool(r["omr"] or r["imslp"] or r["rism"] or r["wikidata"]),
        "+MB": lambda r: bool(r["omr"] or r["imslp"] or r["rism"] or r["wikidata"] or r["musicbrainz"]),
        "+autoridad persona": lambda r: bool(r["confirmed_by_authority"]),
    }
    total = len(ids)
    print("\n=== RESOLUCIÓN ACUMULADA ===")
    for label, pred in levels.items():
        n = sum(1 for r in rows.values() if pred(r))
        print(f"  {label:28} → {n}/{total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
