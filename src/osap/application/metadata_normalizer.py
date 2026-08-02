import re
import unicodedata

from src.osap.domain.music_query_normalizer import MusicQueryNormalizer

_ROLE_MARKERS = {
    "arr": "arranger",
    "arranged by": "arranger",
    "arr.": "arranger",
    "arranger": "arranger",
    "transcr.": "transcriber",
    "transcribed by": "transcriber",
    "transcriber": "transcriber",
    "ed.": "editor",
    "edited by": "editor",
    "editor": "editor",
    "rev.": "editor",
    "revision": "editor",
    "copy": "copier",
    "copier": "copier",
    "orch.": "orchestrator",
    "orchestrated by": "orchestrator",
}

_TITLE_NOISE = re.compile(
    r"\b(WIP|Draft|Version\s*\d*|Rev\.?|Copy|Reduction|Preliminary|Unfinished|Fragment)\b",
    re.IGNORECASE,
)
_ARRANGEMENT_MARKER = re.compile(r"\b(Arr\.?|Transcribed by)\b", re.IGNORECASE)
_YEAR_RANGE = re.compile(r"\(?\d{4}-?\d{4}?\)?")
_CATALOGUE_MARKER = re.compile(
    r"\b(KV|Köchel|Koechel|BWV|Hob\.?|Op\.?|K\.?|D\.?|No\.?)\s*\.?\s*([A-Za-z0-9]+)\b", re.IGNORECASE
)
_TRAILING_CATALOGUE = re.compile(
    r"[,\s]*(KV|Köchel|Koechel|BWV|K\.?|Hob\.?|Op\.?|D\.?|No\.?)\s*\.?\s*([A-Za-z0-9]+)\s*$", re.IGNORECASE
)
_MOJIBAKE = re.compile(r"[\uFFFD]|\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}")
_STRAY_PARENS = re.compile(r"\(([^)]*)\)")

# Known composers for initial expansion: normalized key -> canonical name.
_KNOWN_COMPOSERS: dict[str, str] = {
    "wolfgang amadeus mozart": "Wolfgang Amadeus Mozart",
    "wa mozart": "Wolfgang Amadeus Mozart",
    "w a mozart": "Wolfgang Amadeus Mozart",
    "mozart": "Wolfgang Amadeus Mozart",
    "franz schubert": "Franz Schubert",
    "schubert": "Franz Schubert",
    "ludwig van beethoven": "Ludwig van Beethoven",
    "beethoven": "Ludwig van Beethoven",
    "eduard toldra": "Eduard Toldrà",
    "toldra": "Eduard Toldrà",
    "franz liszt": "Franz Liszt",
    "liszt": "Franz Liszt",
}


class MetadataNormalizer:
    """Cleans raw metadata (composer names, titles) for fuzzy matching and
    groups works. Pure application logic; no domain knowledge of providers."""

    @staticmethod
    def _clean_text(raw: str) -> str:
        text = _MOJIBAKE.sub("", raw)
        text = unicodedata.normalize("NFKC", text)
        return text

    @staticmethod
    def split_roles(raw: str) -> dict[str, str]:
        parts = re.split(
            r"\s+(?:Arr\.?|arr\.?|transcr\.?|ed\.?|edited by|arranged by|transcribed by|orch\.?)\s+",
            raw,
            flags=re.IGNORECASE,
        )
        roles: dict[str, str] = {}
        if not parts:
            return roles
        roles["composer"] = parts[0].strip()
        if len(parts) > 1:
            rest = " ".join(parts[1:])
            marker = next((m for m in _ROLE_MARKERS if m in rest.lower()), None)
            role = _ROLE_MARKERS.get(marker or "arr.", "arranger")
            roles[role] = rest.strip()
        return roles

    @staticmethod
    def canonical_composer(raw: str) -> str:
        text = MetadataNormalizer._clean_text(raw)
        text = _YEAR_RANGE.sub("", text).strip()
        text = re.sub(r"\s+", " ", text)
        key = _collapse_initials(MusicQueryNormalizer.normalize(text))
        return _KNOWN_COMPOSERS.get(key, text)

    @staticmethod
    def catalogue(text: str) -> str | None:
        m = _CATALOGUE_MARKER.search(text)
        if not m:
            return None
        marker = m.group(1).rstrip(".").upper()
        if marker in ("KÖCHEL", "KOECHEL"):
            marker = "K"
        return f"{marker} {m.group(2)}"

    @staticmethod
    def clean_title(raw: str, composer: str | None = None) -> tuple[str, dict[str, str]]:
        text = MetadataNormalizer._clean_text(raw)
        meta: dict[str, str] = {}

        m = re.search(r"\bfor\s+([A-Za-z0-9 ,]+)$", text, re.IGNORECASE)
        if m:
            meta["instrumentation"] = m.group(1).strip()
            text = text[: m.start()].strip()

        cat = MetadataNormalizer.catalogue(text)
        if cat:
            meta["catalogue"] = cat

        # Remove catalogue markers anywhere (not just trailing) so variants like
        # "... KV 618 ..." collapse to the base title.
        text = _CATALOGUE_MARKER.sub("", text)
        text = _TRAILING_CATALOGUE.sub("", text)
        if composer:
            text = _strip_trailing_composer(text, composer)

        text = _TITLE_NOISE.sub("", text)
        text = _ARRANGEMENT_MARKER.sub("", text)
        text = _STRAY_PARENS.sub(lambda m: m.group(1).strip() if m.group(1).strip() else "", text)
        text = re.sub(r"\s{2,}", " ", text).strip(" .-")
        return text or raw.strip(), meta

    @staticmethod
    def work_key(title: str, composer: str | None) -> str:
        parts = []
        if composer:
            parts.append(MusicQueryNormalizer.normalize(MetadataNormalizer.canonical_composer(composer)))
        clean_title, _meta = MetadataNormalizer.clean_title(title, composer)
        parts.append(MusicQueryNormalizer.normalize(clean_title))
        return "|".join(parts)


def _collapse_initials(s: str) -> str:
    """Join consecutive single-letter tokens: 'w a mozart' -> 'wa mozart'."""
    tokens = s.split()
    out: list[str] = []
    i = 0
    while i < len(tokens):
        if len(tokens[i]) == 1:
            j = i
            while j < len(tokens) and len(tokens[j]) == 1:
                j += 1
            out.append("".join(tokens[i:j]))
            i = j
        else:
            out.append(tokens[i])
            i += 1
    return " ".join(out)


def _strip_trailing_composer(title: str, composer: str) -> str:
    """Remove the composer name (or its last name) from the end of a title.

    Handles titles like 'Ave verum corpus Mozart' -> 'Ave verum corpus'.
    """
    comp = composer.strip()
    lowered_title = title.lower()
    if comp.lower() in lowered_title:
        return title[: lowered_title.rindex(comp.lower())].strip(" .-,")
    last = comp.split()[-1].strip(" .,")
    if last and lowered_title.endswith(last.lower()):
        return title[: len(title) - len(last)].strip(" .-,")
    return title
