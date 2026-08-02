import re
import unicodedata


class MusicQueryNormalizer:
    """Normalizes musical search terms for tolerant matching.

    Handles accents, case, whitespace and orthographic noise so that searches
    like 'nocturno' / 'Nocturne' / 'Noctúrnő' converge. Independent of any
    provider.
    """

    @staticmethod
    def normalize(text: str) -> str:
        decomposed = unicodedata.normalize("NFKD", text)
        ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
        ascii_text = ascii_text.lower()
        return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()

    @staticmethod
    def tokens(text: str) -> list[str]:
        normalized = MusicQueryNormalizer.normalize(text)
        return normalized.split()

    @staticmethod
    def matches(haystack: str, needle: str) -> bool:
        """True if all normalized tokens of needle appear in haystack."""
        norm_haystack = MusicQueryNormalizer.normalize(haystack)
        return all(token in norm_haystack for token in MusicQueryNormalizer.tokens(needle))
