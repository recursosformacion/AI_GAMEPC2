import re
import unicodedata

from src.osap.application.metadata_parser import extract_metadata
from src.osap.application.normalized_metadata import NormalizedMetadata
from src.osap.domain.music_query_normalizer import MusicQueryNormalizer

_TITLE_NOISE = re.compile(
    r"\b(WIP|Draft|Version\s*\d*|Rev\.?|Copy|Reduction|Preliminary|Unfinished|Fragment)\b",
    re.IGNORECASE,
)
_ARRANGEMENT_MARKER = re.compile(r"\b(Arr\.?|Transcribed by)\b", re.IGNORECASE)
_YEAR_RANGE = re.compile(r"\(?\d{4}-?\d{4}?\)?")
_MOJIBAKE = re.compile(r"[\uFFFD]|\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}")

_REMOVE_CATALOGUE = re.compile(
    r"\b(?:KV|Köchel|Koechel|K\.?|BWV|Hob\.?|D\.?|Op\.?)\s*\.?\s*[0-9]+[A-Za-z]?\b", re.IGNORECASE
)
_REMOVE_NUMBER = re.compile(r"\b(?:No\.?|Number|Nº)\s*[0-9]+[A-Za-z]?\b", re.IGNORECASE)
_REMOVE_KEY = re.compile(r"\bin\s+[A-H](?:-?flat|b|#|sharp)?(?:\s+(?:major|minor|maj|min))?\b", re.IGNORECASE)
_REMOVE_TRAILING_VOICES = re.compile(r"\s+(?:SATB|SSAATTBB|TTBB|SSA|TTB|SAB)\s*$", re.IGNORECASE)
_REMOVE_TRAILING_SUBTITLE = re.compile(
    r"\s+(?:for\s+[\w'’/-]+(?:\s+[\w'’/-]+)*|a cappella|accompanied)\s*$", re.IGNORECASE
)

_DISPLAY_STOPWORDS = {"in", "the", "of", "and", "for", "an", "on", "to", "op", "et", "da", "di", "de"}

# Known composers for initial expansion: normalized key -> canonical name.
_KNOWN_COMPOSERS: dict[str, str] = {
    "wolfgang amadeus mozart": "Wolfgang Amadeus Mozart",
    "wa mozart": "Wolfgang Amadeus Mozart",
    "w a mozart": "Wolfgang Amadeus Mozart",
    "mozart": "Wolfgang Amadeus Mozart",
    "johann sebastian bach": "Johann Sebastian Bach",
    "js bach": "Johann Sebastian Bach",
    "j s bach": "Johann Sebastian Bach",
    "bach": "Johann Sebastian Bach",
    "ludwig van beethoven": "Ludwig van Beethoven",
    "beethoven": "Ludwig van Beethoven",
    "franz schubert": "Franz Schubert",
    "schubert": "Franz Schubert",
    "giovanni pierluigi da palestrina": "Giovanni Pierluigi da Palestrina",
    "palestrina": "Giovanni Pierluigi da Palestrina",
    "tomas luis de victoria": "Tomás Luis de Victoria",
    "tomás luis de victoria": "Tomás Luis de Victoria",
    "victoria": "Tomás Luis de Victoria",
    "charles gounod": "Charles Gounod",
    "gounod": "Charles Gounod",
    "eduard toldra": "Eduard Toldrà",
    "toldra": "Eduard Toldrà",
    "franz liszt": "Franz Liszt",
    "liszt": "Franz Liszt",
}


class MetadataNormalizer:
    """Produces normalized, comparison-only metadata from a raw title/composer.

    Responsibilities (kept separate by design):
      - `extract_metadata`  -> parser (never modifies the title)
      - `normalize`         -> NormalizedMetadata used ONLY for matching
      - `clean_display_title` / `canonical_composer` -> display helpers

    There is intentionally NO `work_key`/`clean_title`: merging is done by the
    `WorkMatcher` using a scored `MergeDecision`, never by comparing an exact
    concatenated string.
    """

    @staticmethod
    def _clean_text(raw: str) -> str:
        text = _MOJIBAKE.sub("", raw)
        text = unicodedata.normalize("NFKC", text)
        return text

    @staticmethod
    def canonical_composer(raw: str) -> str:
        text = MetadataNormalizer._clean_text(raw)
        # Quitar contenido entre paréntesis (años, notas, "alleged").
        text = re.sub(r"\([^)]*\)", " ", text)
        # Quitar prefijos de catálogo incrustados en el campo compositor ("KV 618 - ...").
        text = _REMOVE_CATALOGUE.sub("", text)
        # Quitar "Composed by" / "by".
        text = re.sub(r"\b(?:composed\s+by|by)\b", " ", text, flags=re.IGNORECASE)
        text = _YEAR_RANGE.sub("", text)
        text = re.sub(r"\s+", " ", text).strip(" ,.-")
        key = _collapse_initials(MusicQueryNormalizer.normalize(text))
        if key in _KNOWN_COMPOSERS:
            return _KNOWN_COMPOSERS[key]
        # Fallback: si el texto limpio contiene un compositor conocido (p. ej.
        # "Wolfgang Amadé Mozart" -> "mozart"), usar el canónico.
        for canonical in _KNOWN_COMPOSERS.values():
            if canonical.split()[-1].lower() in key:
                return canonical
        return text

    @staticmethod
    def comparison_title(title: str, composer: str | None = None) -> str:
        """Normalized title used ONLY for comparison.

        Factors out the structured elements (catalogue, number, key, opus) that
        are tracked separately in `NormalizedMetadata`, strips any trailing
        composer, then lowercases and collapses punctuation/whitespace. It never
        destroys meaningful words ("Symphony", "Dances", "Requiem" are kept).
        """
        text = MetadataNormalizer._clean_text(title)
        text = _REMOVE_CATALOGUE.sub("", text)
        text = _REMOVE_NUMBER.sub("", text)
        text = _REMOVE_KEY.sub("", text)
        if composer:
            canonical = MetadataNormalizer.canonical_composer(composer)
            last = canonical.split()[-1].strip(" .,")
            text = re.sub(rf"\s*\([^)]*{re.escape(last)}[^)]*\)", "", text, flags=re.IGNORECASE)
            text = re.sub(rf"[,\s-]+{re.escape(last)}\s*$", "", text, flags=re.IGNORECASE)
            text = _strip_trailing_composer(text, canonical)
        # Drop parenthetical subtitles/comments ("Requiem (Officium defunctorum)")
        # for comparison; they are not part of the core identity.
        text = re.sub(r"\([^)]*\)", " ", text)
        # Drop trailing voice markers and subtitle phrases ("SATB", "for choir").
        text = _REMOVE_TRAILING_VOICES.sub("", text)
        text = _REMOVE_TRAILING_SUBTITLE.sub("", text)
        # Strip non-meaningful status/role markers (WIP, Draft, arr., ...) so
        # "Ave Verum Corpus" and "Ave Verum Corpus (WIP)" compare as the same.
        text = _TITLE_NOISE.sub("", text)
        text = _ARRANGEMENT_MARKER.sub("", text)
        text = text.lower()
        text = re.sub(r"[^a-z0-9 ]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def normalize(title: str, composer: str | None) -> NormalizedMetadata:
        """Build comparison-only metadata from a raw title + composer."""
        meta = extract_metadata(title)
        return NormalizedMetadata(
            normalized_title=MetadataNormalizer.comparison_title(title, composer),
            normalized_composer=(
                MusicQueryNormalizer.normalize(MetadataNormalizer.canonical_composer(composer)) if composer else None
            ),
            normalized_catalog=meta.catalogue.lower() if meta.catalogue else None,
            normalized_number=meta.work_number,
            normalized_key=meta.key,
        )

    @staticmethod
    def clean_display_title(title: str, composer: str | None = None) -> str:
        """Best-effort display title: removes the catalogue marker (shown
        separately) and any trailing composer clause, then title-cases it. The
        work number and key are preserved. Never returns a broken fragment."""
        text = MetadataNormalizer._clean_text(title)
        text = _REMOVE_CATALOGUE.sub("", text)
        if composer:
            last = composer.split()[-1].strip(" .,")
            text = re.sub(rf"\s*\([^)]*{re.escape(last)}[^)]*\)\s*$", "", text, flags=re.IGNORECASE)
            text = re.sub(rf"[,\s-]+{re.escape(last)}\s*$", "", text, flags=re.IGNORECASE)
            text = _strip_trailing_composer(text, composer)
        text = re.sub(r"\s{2,}", " ", text).strip(" ,;:.-")
        cleaned = MetadataNormalizer._title_case(text)
        return cleaned or title.strip()

    @staticmethod
    def _title_case(value: str) -> str:
        words = value.split()
        out: list[str] = []
        for index, word in enumerate(words):
            low = word.lower()
            if index != 0 and low in _DISPLAY_STOPWORDS:
                out.append(low)
            else:
                out.append(word[:1].upper() + word[1:])
        return " ".join(out)


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
