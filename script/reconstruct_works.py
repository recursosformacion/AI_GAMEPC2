#!/usr/bin/env python
"""FASE 5.7 — reconstrucción por obra: ¿desaparece todavía el registro OMR?

Para cada obra: input → query OMR → respuesta → universo → SimpleUniverseMatcher
(ahora cruza por título ignorando composer=None) → item final.

Muestra si el candidate_missing se resuelve (la obra aparece identificada) o si queda un
segundo problema de recuperación. Usa el matcher actual, sin tocar ranking ni autoridades.

Uso:
    python script/reconstruct_works.py                          # los 3 conocidos
    python script/reconstruct_works.py "Ave Verum Corpus" ...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.osap.infrastructure.resolution.universe_matching import SimpleUniverseMatcher

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace_candidate_missing import _tokenized_fetcher  # noqa: E402

from src.osap.infrastructure.providers.adapters.generic_provider_adapter import ProviderQuery  # noqa: E402

_DEFAULT_WORKS = ["Trip it up Stairs. JJo4.133", "Trunch Wassail Song", "The Galty Rangers"]


def _universe_from_omr(title: str, fetcher) -> list[dict[str, object]]:
    data = fetcher.fetch(None, None, ProviderQuery(query=title, title=title))
    works = data.get("works") if isinstance(data, dict) else []
    universe: list[dict[str, object]] = []
    for w in works:
        if not isinstance(w, dict):
            continue
        universe.append(
            {
                "provider": "omr",
                "work": {
                    "identity": {
                        "id": w.get("id"),
                        "title": w.get("title"),
                        "composer": w.get("composer"),
                        "catalogue": w.get("catalogue"),
                        "confidence": 0.9,
                    }
                },
            }
        )
    return universe


def _reason(item: dict[str, object]) -> str:
    for e in item.get("evidence") or []:
        if isinstance(e, dict) and e.get("kind") == "decision":
            return str(e.get("reason") or "")
    return ""


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("works", nargs="*", default=_DEFAULT_WORKS)
    args = parser.parse_args()

    fetcher = _tokenized_fetcher()
    matcher = SimpleUniverseMatcher()
    for title in args.works:
        universe = _universe_from_omr(title, fetcher)
        items = matcher.match(universe)
        print(f"\n=== {title!r}: OMR devuelve {len(universe)} registros → {len(items)} items ===")
        for it in items:
            resolved = it.get("resolved") or {}
            work = resolved.get("work") or {}
            composer = resolved.get("composer")
            print(f"  status={it['status']} | work={work.get('title')!r} "
                  f"| composer={composer.get('name') if composer else None!r}")
            print(f"  motivo: {_reason(it)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
