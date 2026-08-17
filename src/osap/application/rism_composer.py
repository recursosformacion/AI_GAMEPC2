"""RISM → compositor de una canción/obra.

RISM (Répertoire International des Sources Musicales) cataloga manuscritos musicales. Su
opac (VuFind) expone un search RSS: `Search/Results?lookfor={q}&view=rss`. Los títulos
siguen la convención "Compositor: Obra, ..." → extraemos el compositor (antes del primer
':'). Atribución explícita de la fuente (per ADR-0034): si dice "Anonymus", es atribución.
"""

from __future__ import annotations

import html as _html
import re
import ssl
import urllib.parse
import urllib.request

_OPAC = "https://opac.rism.info/rism/Search/Results"
_UA = "osap-rism-composer/0.1 (reconstruction; read-only)"
_CTX = ssl._create_unverified_context()  # entorno con store de certs roto

_TITLE_RE = re.compile(r"<item>\s*<title>(.*?)</title>", re.S)


def rism_composers(title: str) -> list[str]:
    """Compositores atribuidos por RISM para una obra (del prefijo "Compositor:" del título)."""
    url = f"{_OPAC}?lookfor={urllib.parse.quote(title)}&view=rss"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/xml"}),
            timeout=30,
            context=_CTX,
        ) as response:
            body = response.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return []
    out: list[str] = []
    for match in _TITLE_RE.finditer(body):
        item_title = _html.unescape(match.group(1)).strip()
        composer = _composer_from_item_title(item_title)
        if composer:
            out.append(composer)
    return list(dict.fromkeys(out))


def _composer_from_item_title(item_title: str) -> str | None:
    if not item_title or ":" not in item_title:
        return None
    prefix = item_title.split(":", 1)[0].strip()
    # "Compositor: Obra" — el prefijo es el compositor (o colección).
    prefix = re.sub(r"\([^)]*\)", "", prefix).strip()
    if not prefix or len(prefix) < 2:
        return None
    return prefix
