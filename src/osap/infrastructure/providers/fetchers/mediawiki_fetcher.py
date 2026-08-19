"""Level-2 protocol adapter for IMSLP.

Talks to the IMSLP MediaWiki API and returns JSON equivalent to the provider contract
(`works` -> list of Work dicts). The result flows through the same mapping pipeline as
any Level-1 REST provider. Only protocol-specific logic (MediaWiki query params, page
URLs, composer extraction) lives here.
"""

import hashlib
import re

from src.osap.infrastructure.mediawiki import MediaWikiClient
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    Endpoint,
    ProviderDefinition,
    ProviderFetcher,
    ProviderQuery,
)

_COPOSER_CATEGORY_RE = re.compile(r"Works by (.+)")
_WORK_TITLE_RE = re.compile(r"\(.+\)")
_NON_WORK_PREFIXES = (
    "List of",
    "Wishlist",
    "Category:",
    "Special:",
    "IMSLP:",
    "Template:",
    "File:",
    "Help:",
    "User:",
    "Talk:",
    "Edition ",
)


class MediaWikiFetcher(ProviderFetcher):
    """IMSLP (MediaWiki) -> normalized contract JSON."""

    def __init__(self, mw: MediaWikiClient) -> None:
        self._mw = mw

    def fetch(
        self, definition: ProviderDefinition, endpoint: Endpoint, query: ProviderQuery
    ) -> dict[str, object] | None:
        text = _build_search(query)
        if not text:
            return {"works": []}
        raw = self._mw.search(text, namespace=0, limit=100)
        works: list[dict[str, object]] = []
        for result in raw:
            title = str(result.get("title") or "")
            snippet = str(result.get("snippet") or "")
            if not title or _is_non_work(title, snippet):
                continue
            works.append(_to_work(title, result))
        return {"works": works}

    def fetch_resource(
        self, definition: ProviderDefinition, endpoint: Endpoint, work_id: str
    ) -> dict[str, object] | None:
        return None


def _to_work(title: str, result: dict[str, object]) -> dict[str, object]:
    snippet = str(result.get("snippet") or "")
    composer = _extract_composer(title)
    public_domain: bool | None = None
    if snippet:
        low = snippet.lower()
        if "public domain" in low:
            public_domain = True
        elif any(w in low for w in ("copyright", "©", "all rights reserved", "non-commercial")):
            public_domain = False
    page_url = str(result.get("descriptionurl") or f"https://imslp.org/wiki/{title.replace(' ', '_')}")
    remote_id = str(result.get("pageid") or _hash(title))
    work_id = _hash(title)
    return {
        "id": work_id,
        "title": title,
        "composer": composer,
        "catalogue": None,
        "license": "public domain" if public_domain is True else None,
        "public_domain": public_domain,
        "resources": [
            {
                "id": remote_id,
                "format": "pdf",
                "mime_type": "application/pdf",
                "available": False,
                "license": "public domain" if public_domain is True else None,
                "download_url": page_url,
                "view_url": page_url,
                "thumbnail_url": None,
            }
        ],
    }


def _build_search(query: ProviderQuery) -> str:
    parts: list[str] = []
    if query.title or query.query:
        parts.append(query.title or query.query or "")
    if query.composer:
        parts.append(query.composer)
    return " ".join(parts).strip()


def _is_non_work(title: str, snippet: str) -> bool:
    if title.startswith(_NON_WORK_PREFIXES) or snippet.startswith("#REDIRECT"):
        return True
    return not bool(_WORK_TITLE_RE.search(title))


def _extract_composer(title: str) -> str | None:
    match = re.search(r"\((.+)\)", title)
    if not match:
        return None
    inner = match.group(1)
    parts = inner.rsplit(",", 1)
    if len(parts) == 2:
        return f"{parts[1].strip()} {parts[0].strip()}"
    return inner.strip() or None


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]  # noqa: S324
