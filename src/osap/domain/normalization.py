import hashlib
import re
import unicodedata


def normalize_name(value: str) -> str:
    """Normalize a musical name for loose matching: strip accents, lowercase, collapse spaces."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).strip().lower()


def stable_id(*parts: object, length: int = 16) -> str:
    """Deterministic short id from arbitrary parts (stable across processes and restarts).

    Unlike ``abs(hash(...))`` (randomized per process via PYTHONHASHSEED), this digest is
    reproducible, which the determinism principle of OSAP requires for identity ids.
    """
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]
