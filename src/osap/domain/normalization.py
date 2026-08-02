import re
import unicodedata


def normalize_name(value: str) -> str:
    """Normalize a musical name for loose matching: strip accents, lowercase, collapse spaces."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).strip().lower()
