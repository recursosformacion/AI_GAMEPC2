"""Documentos de índice V6 y comprobación de estabilidad de URLs.

El feed de Storage ya trae `work_id = index-<works.id>` y el título de la Work.
El índice no debe inventar identidad: conserva ese `work_id` y deriva el slug con
la misma función que la web (`work_canonical_slug`). Cualquier cambio de título o
de slug exige tabla de correspondencia y 301.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from src.osap.api.seo.slug import normalize_work_id, work_canonical_slug


@dataclass(frozen=True)
class V6IndexDocument:
    public_id: str
    title: str
    slug: str
    composer: str | None = None
    resources: list[dict[str, Any]] = field(default_factory=list)


def document_from_feed(item: dict[str, Any]) -> V6IndexDocument:
    """Convierte un elemento del feed V6 en documento de índice estable."""
    raw_id = str(item.get("work_id") or "").strip()
    normalized = normalize_work_id(raw_id)
    if normalized is None:
        raise ValueError(f"work_id no válido en el feed V6: {raw_id!r}")
    title = str(item.get("title") or "").strip()
    return V6IndexDocument(
        public_id=normalized,
        title=title,
        slug=work_canonical_slug(title),
        composer=(str(item["composer"]).strip() or None) if item.get("composer") else None,
        resources=list(item.get("resources") or []),
    )


def parse_sitemap_work_url(url: str) -> tuple[str, str] | None:
    """Extrae `(work_id, slug)` de `/obras/<work_id>/<slug>`."""
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 3 or parts[0] != "obras":
        return None
    return parts[1], parts[2]


def compare_sitemap(
    urls: list[str], documents: dict[str, V6IndexDocument]
) -> dict[str, Any]:
    """Compara URLs del sitemap con los documentos canónicos V6.

    Un slug distinto con el mismo `work_id` se considera histórico (la URL debe
    seguir resolviendo); no es un fallo del índice, pero se reporta.
    """
    checked = 0
    missing_document = 0
    canonical_match = 0
    historical_slug = 0
    malformed = 0
    samples: list[dict[str, str]] = []
    for url in urls:
        parsed = parse_sitemap_work_url(url)
        if parsed is None:
            malformed += 1
            continue
        work_id, slug = parsed
        document = documents.get(work_id)
        if document is None:
            missing_document += 1
            if len(samples) < 10:
                samples.append({"url": url, "reason": "missing_document"})
            continue
        checked += 1
        if document.slug == slug:
            canonical_match += 1
        else:
            historical_slug += 1
            if len(samples) < 10:
                samples.append(
                    {
                        "url": url,
                        "reason": "historical_slug",
                        "canonical_slug": document.slug,
                    }
                )
    return {
        "checked": checked,
        "missing_document": missing_document,
        "canonical_match": canonical_match,
        "historical_slug": historical_slug,
        "malformed": malformed,
        "samples": samples,
    }
