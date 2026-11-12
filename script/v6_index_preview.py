"""Previsualización del índice V6 desde el feed de Storage.

No escribe el índice de OSAP. Construye documentos canónicos
(`index-<works.id>` + slug desde `works_title`), puede volcarlos a un SQLite de
staging y compararlos con el índice actual y/o un sitemap.

Uso:
    python script/v6_index_preview.py --feed var/v6-feed.json --sitemap var/works-1.xml
    python script/v6_index_preview.py --feed var/v6-feed.json --index --stage-db var/v6-index.sqlite3
    python script/v6_index_preview.py --feed-url http://127.0.0.1:8000/api/v6/index/works
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import tomllib
from pathlib import Path

import httpx
import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.osap.api.seo.slug import work_canonical_slug  # noqa: E402
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


def _write_stage(documents: dict, path: Path, current_titles: dict[str, str]) -> int:
    """Escribe staging conservando el título/slug del índice para IDs existentes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for doc in documents.values():
        title = current_titles.get(doc.public_id, doc.title)
        slug = work_canonical_slug(title) if doc.public_id in current_titles else doc.slug
        source = "index" if doc.public_id in current_titles else "feed"
        rows.append((doc.public_id, title, slug, doc.composer, source))
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE IF EXISTS index_works")
        conn.execute(
            "CREATE TABLE index_works (public_id TEXT PRIMARY KEY, title TEXT, "
            "slug TEXT, composer TEXT, title_source TEXT)"
        )
        conn.executemany(
            "INSERT INTO index_works (public_id, title, slug, composer, title_source) "
            "VALUES (?,?,?,?,?)",
            rows,
        )
    return len(rows)


def _index_titles(documents: dict, root: Path) -> dict[str, str]:
    config_path = root / "osap.toml"
    if not config_path.exists():
        raise SystemExit("Falta osap.toml para comparar con el índice actual")
    cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))["db"]
    conn = pymysql.connect(
        host=cfg["host"], port=int(cfg.get("port", 3306)), user=cfg["user"],
        password=cfg["password"], database=cfg["name"], charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    current: dict[str, str] = {}
    ids = list(documents)
    with conn.cursor() as cur:
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            placeholders = ",".join(["%s"] * len(chunk))
            cur.execute(
                f"SELECT public_id, title FROM index_works WHERE public_id IN ({placeholders})",
                chunk,
            )
            for row in cur.fetchall():
                current[str(row["public_id"])] = str(row.get("title") or "")
    conn.close()
    return current


def _compare_index(documents: dict, current: dict[str, str]) -> dict:
    ids = list(documents)
    feed_not_in_index = [pid for pid in ids if pid not in current]
    title_changed = [
        (pid, current[pid], documents[pid].title)
        for pid in ids
        if pid in current and current[pid] != documents[pid].title
    ]
    slug_changed = [
        (pid, work_canonical_slug(current[pid]), documents[pid].slug)
        for pid in ids
        if pid in current
        and documents[pid].slug != work_canonical_slug(current[pid])
    ]
    return {
        "feed_documents": len(documents),
        "present_in_index": len(current),
        "feed_not_in_index": len(feed_not_in_index),
        "title_changed": len(title_changed),
        "slug_changed": len(slug_changed),
        "title_samples": title_changed[:10],
        "slug_samples": slug_changed[:10],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run del índice V6 (sin escribir OSAP).")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--feed", help="Fichero JSON con el feed V6.")
    source.add_argument("--feed-url", help="URL del feed /api/v6/index/works.")
    parser.add_argument("--sitemap", help="Sitemap XML de works para comparar.")
    parser.add_argument("--sitemap-limit", type=int, default=500)
    parser.add_argument("--feed-pages", type=int, default=20)
    parser.add_argument("--token", default=os.environ.get("OSAP_STORAGE_SERVICE_TOKEN", ""))
    parser.add_argument("--stage-db", help="SQLite de staging para los documentos.")
    parser.add_argument("--index", action="store_true", help="Comparar con el índice actual.")
    parser.add_argument("--out", help="Informe JSON opcional.")
    args = parser.parse_args()

    items = _read_feed_file(Path(args.feed)) if args.feed else _fetch_feed(
        args.feed_url, args.token or None, args.feed_pages
    )

    documents: dict[str, object] = {}
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
    current_titles = (
        _index_titles(documents, ROOT) if (args.index or args.stage_db) else {}
    )
    if args.index:
        summary["index_comparison"] = _compare_index(documents, current_titles)
    if args.stage_db:
        summary["stage_rows"] = _write_stage(
            documents, Path(args.stage_db), current_titles
        )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if args.sitemap:
        sitemap = summary["sitemap"]
        if isinstance(sitemap, dict) and (
            sitemap.get("missing_document") or sitemap.get("malformed")
        ):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
