"""Previsualización del índice V6 desde el feed de Storage.

No escribe el índice. Construye documentos canónicos (`index-<works.id>` + slug
desde `works_title`) y compara una muestra de sitemap para detectar cualquier
cambio de URL antes del corte.

Uso:
    python script/v6_index_preview.py --feed var/v6-feed.json --sitemap var/works-1.xml
    python script/v6_index_preview.py --feed-url http://127.0.0.1:8000/api/v6/index/works
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.osap.application.v6_index import (  # noqa: E402
    compare_sitemap,
    document_from_feed,
)

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


def _read_feed_file(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    raise SystemExit("El feed debe ser una lista o un objeto con 'items'.")


def _fetch_feed(url: str, token: str | None, pages: int) -> list[dict]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    items: list[dict] = []
    cursor = 0
    with httpx.Client(timeout=30, headers=headers) as client:
        for _ in range(max(1, pages)):
            response = client.get(url, params={"cursor": cursor, "limit": 500})
            response.raise_for_status()
            body = response.json()
            page_items = body.get("items") or []
            items.extend(page_items)
            next_cursor = body.get("next_cursor")
            if not page_items or next_cursor is None:
                break
            cursor = int(next_cursor)
    return items


def _sitemap_urls(path: Path, limit: int) -> list[str]:
    text = path.read_text(encoding="utf-8")
    urls = [url for url in _LOC_RE.findall(text) if "/obras/" in url]
    return urls[: max(1, limit)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run del índice V6 (sin escribir).")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--feed", help="Fichero JSON con el feed V6.")
    source.add_argument("--feed-url", help="URL del feed /api/v6/index/works.")
    parser.add_argument("--sitemap", help="Sitemap XML de works para comparar.")
    parser.add_argument("--sitemap-limit", type=int, default=500)
    parser.add_argument("--feed-pages", type=int, default=20)
    parser.add_argument("--token", default=os.environ.get("OSAP_STORAGE_SERVICE_TOKEN", ""))
    parser.add_argument("--out", help="Informe JSON opcional.")
    args = parser.parse_args()

    if args.feed:
        items = _read_feed_file(Path(args.feed))
    else:
        items = _fetch_feed(args.feed_url, args.token or None, args.feed_pages)

    documents = {}
    invalid: list[str] = []
    for item in items:
        try:
            document = document_from_feed(item)
        except ValueError as exc:
            invalid.append(str(exc))
            continue
        documents[document.public_id] = document

    summary: dict[str, object] = {
        "feed_items": len(items),
        "documents": len(documents),
        "invalid": len(invalid),
        "invalid_samples": invalid[:10],
    }
    if args.sitemap:
        comparison = compare_sitemap(
            _sitemap_urls(Path(args.sitemap), args.sitemap_limit), documents
        )
        summary["sitemap"] = comparison
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if comparison["missing_document"] or comparison["malformed"]:
            raise SystemExit(1)
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.out:
        Path(args.out).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
