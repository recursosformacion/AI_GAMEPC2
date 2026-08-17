"""Wikipedia → compositor de una canción/obra.

Cuando una canción está identificada, busca su artículo en Wikipedia (en.wikipedia.org) y
extrae el compositor del wikitexto: infobox `| composer =`, frase inicial "... by X", o
categoría "Compositions by X". Es una fuente más de atribución (no la única ni la última:
la validación contra autoridad es aparte).
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.parse
import urllib.request

_WIKI = "https://en.wikipedia.org/w/api.php"
_UA = "osap-wiki-song-composer/0.1 (reconstruction; read-only)"
_CTX = ssl._create_unverified_context()  # entorno con store de certs roto

_INFOBOX_COMPOSER = re.compile(r"\|\s*composer\s*=\s*([^\n|]+)", re.IGNORECASE)
_FIRST_SENTENCE_BY = re.compile(r"\bby\s+([A-Z][\w'.\-& ]+?)\.", re.IGNORECASE)
_CATEGORY_COMPOSER = re.compile(
    r"\[\[Category:(?:Compositions by|Works by|Music by|Songs by)\s+([^\]]+)\]\]", re.IGNORECASE
)
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_TEMPLATE = re.compile(r"\{\{[^}]*\}\}")


def wikipedia_composer(title: str) -> str | None:
    page = _search(title)
    if not page:
        return None
    wikitext = _wikitext(page)
    if not wikitext:
        return None
    composer = _extract_composer(wikitext)
    return composer


def _api(params: dict[str, str]) -> dict[str, object]:
    url = f"{_WIKI}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"}),
            timeout=25,
            context=_CTX,
        ) as response:
            data = json.loads(response.read())
            return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _search(title: str) -> str | None:
    doc = _api(
        {
            "action": "query",
            "list": "search",
            "srsearch": title,
            "srlimit": "3",
            "format": "json",
            "formatversion": "2",
        }
    )
    query = doc.get("query")
    results = query.get("search") if isinstance(query, dict) else None
    if isinstance(results, list) and results and isinstance(results[0], dict):
        return str(results[0].get("title") or "")
    return None


def _wikitext(title: str) -> str | None:
    doc = _api(
        {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "titles": title,
            "format": "json",
            "formatversion": "2",
        }
    )
    try:
        query = doc.get("query")
        if not isinstance(query, dict):
            return None
        pages = query.get("pages")
        if not isinstance(pages, list) or not pages or not isinstance(pages[0], dict):
            return None
        page = pages[0]
        revisions = page.get("revisions")
        if not isinstance(revisions, list) or not revisions or not isinstance(revisions[0], dict):
            return None
        slots = revisions[0].get("slots")
        if not isinstance(slots, dict):
            return None
        main = slots.get("main")
        content = main.get("content") if isinstance(main, dict) else None
        return str(content) if content else None
    except Exception:  # noqa: BLE001
        return None


def _extract_composer(wikitext: str) -> str | None:
    text = _TEMPLATE.sub(" ", wikitext)

    m = _INFOBOX_COMPOSER.search(text)
    if m:
        return _clean_name(m.group(1))

    # Primera frase: "X is a ... by Composer."
    lead = text[:1200]
    lead = _WIKILINK.sub(r"\1", lead)
    m = _FIRST_SENTENCE_BY.search(lead)
    if m:
        return _clean_name(m.group(1))

    m = _CATEGORY_COMPOSER.search(text)
    if m:
        return _clean_name(m.group(1))
    return None


def _clean_name(raw: str) -> str | None:
    name = raw.strip()
    name = re.sub(r"\([^)]*\)", "", name).strip()
    name = _WIKILINK.sub(r"\1", name).strip()
    if not name or len(name) < 2:
        return None
    return name
