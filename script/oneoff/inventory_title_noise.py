#!/usr/bin/env python
"""FASE 5.7.2 — Inventario de patrones de ruido en títulos (ANTES de implementar reglas).

Para los casos candidate_missing reales (39, 23, 62, 142) y sus variantes OMR, muestra:
    raw → comparison_title actual → clases de ruido detectadas → clave de identidad esperada.

Objetivo: diseñar 2–4 reglas canónicas y trazables, no excepciones por título.

Uso:
    python script/inventory_title_noise.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import ProviderQuery

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trace_candidate_missing  # noqa: E402

# Casos candidate_missing reales: id -> (título input, clave de identidad esperada)
_CASES = {
    "39": ("Mr. Riley", "mr riley"),
    "23": ("The Regency Waltz", "regency waltz"),
    "62": ("Trip up Stairs", "trip up stairs"),
    "142": ("GOD SAVE THE KING", "god save the king"),
}

_CATALOG_SUFFIX_RE = re.compile(r"\s+[A-Za-z]{1,5}\.?\d+(?:\.\d+)*[A-Za-z]?\s*$", re.I)
_TRAILING_DASH = re.compile(r"\s+[-—]\s+")
_LEADING_ARTICLE = re.compile(r"^(?:a|an|the)\s+", re.I)
_EMBEDDED_ID = re.compile(r"\b(?:ID\s*\d|\b\d{3,4}\b)\b", re.I)
_PUNCTUATION = re.compile(r"[^\w\s'-]")


def noise_classes(title: str) -> list[str]:
    out: list[str] = []
    if _CATALOG_SUFFIX_RE.search(title):
        out.append("catalog_suffix")
    if _LEADING_ARTICLE.search(title):
        out.append("leading_article")
    if _TRAILING_DASH.search(title):
        out.append("trailing_dash")
    if _EMBEDDED_ID.search(title):
        out.append("embedded_id")
    if _PUNCTUATION.search(title):
        out.append("punctuation")
    return out


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    fetcher = trace_candidate_missing._tokenized_fetcher()
    for cid, (input_title, expected) in _CASES.items():
        data = fetcher.fetch(None, None, ProviderQuery(query=input_title, title=input_title))
        works = data.get("works") if isinstance(data, dict) else []
        # variantes únicas de título
        variants = sorted({str(w.get("title")) for w in works if isinstance(w, dict)})
        print("=" * 72)
        print(f"[{cid}] input: {input_title!r}  → identidad esperada: {expected!r}")
        print(f"  {len(variants)} variante(s):")
        for v in variants:
            ct = MetadataNormalizer.comparison_title(v)
            cls = noise_classes(v)
            same = "SÍ" if ct == expected else "no"
            print(f"    raw={v!r}")
            print(f"      comparison_title={ct!r}  coincide_esperada={same}  ruido={cls}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
