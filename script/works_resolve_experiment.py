#!/usr/bin/env python3
"""Experimento v1 de /works/resolve (250 obras).

Lee un fichero JSON con `{"works": [{...}]}`, llama a `POST /api/v1/works/resolve`
con concurrencia baja y calcula las métricas del experimento:

  - resolved / ambiguous / not_found
  - compositor null (obra identificada sin autor)
  - input_quality = corrupt_or_suspicious (problema real de ingestión)
  - proveedores que aportan evidencia (por estado)

Además guarda una muestra por grupo para revisión manual (un resolved incorrecto es
mucho peor que un ambiguous).

Uso:
    python script/works_resolve_experiment.py works.json [--base URL] [--concurrency 4]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

DEFAULT_BASE = "http://osap-app/api/v1"


def resolve_batch(base: str, works: list[dict], concurrency: int) -> dict:
    payload = json.dumps({"works": works, "concurrency": concurrency}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/works/resolve",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment runner for /works/resolve")
    parser.add_argument("works_file", help="JSON file with {'works': [...]}")
    parser.add_argument("--base", default=DEFAULT_BASE, help="API base URL (default %(default)s)")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--samples", type=int, default=5, help="samples per status to print")
    args = parser.parse_args()

    works = json.loads(Path(args.works_file).read_text("utf-8")).get("works", [])
    if not works:
        print("No works in file", file=sys.stderr)
        return

    data = resolve_batch(args.base, works, args.concurrency)
    payload = data.get("data", {}) if isinstance(data, dict) else {}
    results = payload.get("results", [])
    summary = payload.get("summary", {})

    status_counts = Counter(r["status"] for r in results)
    composer_null = sum(1 for r in results if (r.get("resolved") or {}).get("composer") is None)
    corrupt = sum(1 for r in results if r.get("input_quality") == "corrupt_or_suspicious")
    suspicious = sum(1 for r in results if r.get("input_quality") == "suspicious")
    provider_counts: Counter[str] = Counter()
    for r in results:
        for e in r.get("evidence", []):
            provider_counts[e["provider"]] += 1

    print("\n=== RESUMEN /works/resolve ===")
    print(f"total              : {summary.get('total', len(results))}")
    for s in ("resolved", "ambiguous", "not_found"):
        print(f"  {s:17}: {summary.get(s, status_counts.get(s, 0))}")
    print(f"composer null      : {composer_null}")
    print(f"input corrupt      : {corrupt}")
    print(f"input suspicious   : {suspicious}")
    print("\n=== PROVEEDORES QUE APORTAN EVIDENCIA ===")
    for provider, n in provider_counts.most_common():
        print(f"  {provider:20}: {n}")

    print("\n=== MUESTRA POR ESTADO (revisar manualmente) ===")
    for status in ("resolved", "ambiguous", "not_found"):
        group = [r for r in results if r["status"] == status]
        print(f"\n--- {status} ({len(group)}) ---")
        for r in group[: args.samples]:
            res = r.get("resolved") or {}
            comp = (res.get("composer") or {}).get("name")
            work = (res.get("work") or {}).get("title")
            norm = r.get("normalized", {})
            print(
                f"  [{r.get('id')}] norm_title={norm.get('title')!r} "
                f"norm_composer={norm.get('composer')!r} -> resolved={work!r} / {comp!r} "
                f"conf={r.get('confidence')} iq={r.get('input_quality')}"
            )


if __name__ == "__main__":
    main()
