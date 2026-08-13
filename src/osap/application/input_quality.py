"""Input-quality classification for composer resolution (v1).

The raw composer name is never substituted; `classify_input_quality` just flags how
trustworthy the input looks so the resolution does not treat a clearly corrupt name the
same as a normal one. Levels:
  - `normal`: looks like a real composer name.
  - `suspicious`: unusually short or oddly shaped, but not obviously corrupt.
  - `corrupt_or_suspicious`: mojibake, replacement chars, or mostly non-letters.
"""

import re

_REPLACEMENT = re.compile(r"[\uFFFD]")
_MOJIBAKE_ARTIFACT = re.compile(r"[ªº§±¶¿¡]")
_HEX_ESCAPE = re.compile(r"\\[xXuU][0-9a-fA-F]{2,4}")


def classify_input_quality(raw: str) -> str:
    """Return `normal`, `suspicious` or `corrupt_or_suspicious` for a composer name."""
    text = (raw or "").strip()
    if not text:
        return "corrupt_or_suspicious"
    if _REPLACEMENT.search(text) or _MOJIBAKE_ARTIFACT.search(text) or _HEX_ESCAPE.search(text):
        return "corrupt_or_suspicious"

    letters = sum(1 for ch in text if ch.isalpha())
    if letters == 0:
        return "corrupt_or_suspicious"

    tokens = text.split()
    single_letters = [t for t in tokens if len(t) == 1 and t.isalpha()]

    if len(text) <= 2:
        return "suspicious"
    # A run of isolated single letters mixed with accents (e.g. "ä æ R Z H çèª")
    # is almost always corrupted data, not a real name.
    if len(single_letters) >= 2 and letters <= 6:
        return "corrupt_or_suspicious"
    if len(single_letters) >= 1 and len(text) <= 12:
        return "suspicious"
    return "normal"
