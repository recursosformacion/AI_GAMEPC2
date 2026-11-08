#!/usr/bin/env python
"""Investigar los candidate_missing supervivientes (19, 130, 112, 108, 18).

Muestra input → raw OMR → items del matcher → query limpio, para clasificar el fallo
(recuperación, formato de título, alias, o normalización).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import ProviderQuery
from src.osap.infrastructure.resolution.universe_matching import SimpleUniverseMatcher

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trace_candidate_missing  # noqa: E402

_IDS = ["19", "130", "112", "108", "18"]


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sample = json.loads((Path(__file__).resolve().parent / "works250.sample.json").read_text(encoding="utf-8"))["items"]
    fetcher = trace_candidate_missing._tokenized_fetcher()
    matcher = SimpleUniverseMatcher()
    for cid in _IDS:
        title = str(sample[cid].get("note") or "")
        data = fetcher.fetch(None, None, ProviderQuery(query=title, title=title))
        works = data.get("works") if isinstance(data, dict) else []
        print("=" * 72)
        print(f"[{cid}] input: {title!r}")
        print("  OMR raw:")
        for w in works:
            print(f"    id={w.get('id')} title={w.get('title')!r} comp={w.get('composer')!r}")
        universe = [
            {"provider": "omr", "work": {"identity": {
                "id": w.get("id"), "title": w.get("title"), "composer": w.get("composer"), "confidence": 0.9,
            }}}
            for w in works
        ]
        items = matcher.match(universe)
        print("  items del matcher:")
        for it in items:
            n = it.get("normalized", {})
            print(
                f"    norm_title={n.get('title')!r} raw={n.get('title_raw')!r} "
                f"comp={n.get('composer')!r} status={it['status']}"
            )
        clean, comp = MetadataNormalizer.extract_composer_from_title(title)
        print(f"  query limpio (matcher) = {MetadataNormalizer.comparison_title(clean, comp or '')!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
