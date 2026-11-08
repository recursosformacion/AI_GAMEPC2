#!/usr/bin/env python
"""Diagnóstico de `candidate_missing`: ¿en qué punto desaparece una obra que existe?

Reconstruye el recorrido input → title_raw → normalized → query OMR → (búsqueda directa)
para casos que terminaron en `not_found`/`candidate_missing`. Diferencia:

  A. la query ya nace mal (título con sufijos de catálogo, etc.)
  B. la query es correcta pero OMR no devuelve el registro (recuperación/indexación)
  C. OMR devuelve el registro pero lo descartamos (extracción/filtro)

La búsqueda directa en OMR requiere token `storage:read`; sin él, se reporta la traza de
construcción de query (A) y el 401 (B/C no comprobables sin credenciales).

Uso:
    python script/trace_candidate_missing.py            # 94, 32, 102
    python script/trace_candidate_missing.py 94 32 102
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import ProviderQuery
from src.osap.infrastructure.providers.fetchers.omr_fetcher import OmrStorageFetcher

_DEFAULT_RESULTS = Path(__file__).resolve().parent / "works250.results.json"


def _omr_query(composer: str, title: str, query: str) -> str:
    # Replica OmrStorageFetcher._build_query: compositor > título > query cruda.
    if composer:
        return composer
    if title:
        return title
    return (query or "").strip()


def progressive_variants(raw: str) -> list[str]:
    """Variantes progresivas de la query para localizar dónde aparece el registro."""
    variants = [raw.strip()]
    cleaned = raw.strip()
    # Quitar sufijos de catálogo/numéricos tipo "JJo4.133", "K.618", "BWV...".
    cleaned = re.sub(r"\s+[A-Za-z]+\.?\d+(?:\.\d+)*\s*$", "", cleaned).strip()
    if cleaned and cleaned != raw.strip():
        variants.append(cleaned)
    # Quitar artículo inicial "The".
    no_the = re.sub(r"^the\s+", "", cleaned.lower()).strip()
    if no_the and no_the != cleaned.lower():
        variants.append(no_the.title())
    # Forma normalizada de comparación.
    norm = MetadataNormalizer.comparison_title(raw)
    if norm and norm not in variants:
        variants.append(norm)
    return variants


def trace(results: list[dict[str, object]], ids: list[str]) -> int:
    res = {str(r.get("id")): r for r in results}
    for i in ids:
        r = res.get(i)
        if not r:
            print(f"\n[{i}] no encontrado en results")
            continue
        n = r.get("normalized") or {}
        raw_title = str(n.get("title_raw") or "")
        composer = str(n.get("composer_raw") or "")
        query = _omr_query(composer, raw_title, str(r.get("query") or ""))
        print(f"\n=== [{i}] status={r.get('status')} === input: {raw_title!r}")
        print(f"  composer_raw: {composer!r}")
        print(f"  title (norm): {MetadataNormalizer.comparison_title(raw_title)!r}")
        print(f"  query que enviaría OMR: {query!r}")
        print("  variantes progresivas:")
        for v in progressive_variants(raw_title):
            print(f"    - {v!r}")
    return 0


def _tokenized_fetcher() -> OmrStorageFetcher:
    """Fetcher OMR autenticado usando la configuración del propio osap-api.

    Requiere OSAP_SERVICE_CLIENT_ID / OSAP_SERVICE_CLIENT_SECRET + rutas de osap-auth.
    """
    from src.osap.bootstrap.configuration import load_configuration
    from src.osap.bootstrap.wiring import _routes
    from src.osap.infrastructure.auth.service_token_provider import (
        ClientCredentialsServiceTokenProvider,
    )

    cfg = load_configuration()
    routes, _ = _routes(cfg.deployment, cfg.dev_mode)
    token_provider = ClientCredentialsServiceTokenProvider(
        client_id=cfg.service_client_id or "osap-api",
        client_secret=cfg.service_client_secret or "",
        token_url=routes["auth_token"],
    )
    return OmrStorageFetcher(base_url=routes["storage"], token_provider=token_provider)


def live_search(ids: list[str], results: list[dict[str, object]]) -> None:
    res = {str(r.get("id")): r for r in results}
    fetcher = _tokenized_fetcher()
    for i in ids:
        r = res.get(i)
        if not r:
            continue
        raw_title = str((r.get("normalized") or {}).get("title_raw") or "")
        print(f"\n--- búsqueda directa OMR [{i}] {raw_title!r} ---")
        for v in progressive_variants(raw_title):
            print(f"  query {v!r} -> ", end="")
            try:
                data = fetcher.fetch(None, None, ProviderQuery(query=v, title=v))
            except Exception as e:  # noqa: BLE001
                print(f"ERROR {e}")
                continue
            works = data.get("works") if isinstance(data, dict) else []
            print(f"{len(works)} resultados")


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*", default=["94", "32", "102"], help="ids de works250.results.json")
    parser.add_argument("--results", type=Path, default=_DEFAULT_RESULTS)
    parser.add_argument("--live", action="store_true", help="Intenta la búsqueda directa en OMR (requiere token)")
    args = parser.parse_args()
    if not args.results.exists():
        print(f"No existe: {args.results}", file=sys.stderr)
        return 2
    doc = json.loads(args.results.read_text(encoding="utf-8"))
    results = doc.get("results") if isinstance(doc.get("results"), list) else []
    trace(results, args.ids)
    if args.live:
        live_search(args.ids, results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
