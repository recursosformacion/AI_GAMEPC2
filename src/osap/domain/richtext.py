"""Saneado de HTML para el cuerpo de artículos (allowlist, sin dependencias externas).

Los autores pueden escribir el cuerpo como **texto plano** (párrafos separados por líneas en
blanco) o como **HTML sencillo** (`<p>`, `<strong>`, `<em>`, listas, enlaces…). El HTML se
sanea con una allowlist: se descartan etiquetas/atributos no permitidos y todo `script`/`style`,
y los enlaces se restringen a `http(s)`/`mailto`/relativos. Nunca se acepta HTML arbitrario.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

_ALLOWED_TAGS = frozenset(
    {"p", "br", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li", "h2", "h3", "h4", "blockquote", "a", "hr"}
)
_VOID_TAGS = frozenset({"br", "hr"})
_DROP_CONTENT_TAGS = frozenset({"script", "style"})
_SAFE_SCHEMES = ("http://", "https://", "mailto:")
_TAG_DETECT = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")


def looks_like_html(text: str | None) -> bool:
    """Heurística: ¿el cuerpo contiene etiquetas HTML?"""
    return bool(text) and _TAG_DETECT.search(text or "") is not None


def _safe_href(value: str | None) -> str | None:
    href = (value or "").strip()
    if not href:
        return None
    lowered = href.lower()
    if lowered.startswith(_SAFE_SCHEMES) or href.startswith("/") or href.startswith("#"):
        return href
    return None


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS:
            self._skip += 1
            return
        if tag not in _ALLOWED_TAGS:
            return
        if tag == "a":
            href = _safe_href(dict(attrs).get("href"))
            if href is not None:
                self._parts.append(f'<a href="{escape(href, quote=True)}" rel="nofollow noopener">')
            else:
                self._parts.append("<a>")
        else:
            self._parts.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self._parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            self._parts.append(escape(data, quote=False))

    def result(self) -> str:
        return "".join(self._parts)


def sanitize_html(html: str) -> str:
    """Devuelve solo el HTML permitido (allowlist); descarta el resto."""
    parser = _Sanitizer()
    parser.feed(html or "")
    parser.close()
    return parser.result()


def sanitize_body(body: str) -> str:
    """Sanea el cuerpo si parece HTML; si es texto plano, se devuelve tal cual."""
    return sanitize_html(body) if looks_like_html(body) else (body or "")
