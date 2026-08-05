"""Metadata extraction for musical works.

This module is PURE extraction: it parses structured elements (catalogue,
work number, key, opus) out of a raw title WITHOUT modifying the original
title. The display title is always the raw title; extraction only feeds the
``NormalizedMetadata`` (comparison-only) used by the ``WorkGroupingMatcher``.

Separation of concerns (required by the project):
  1. Extract metadata   -> here, never touches the title
  2. Normalize          -> ``MetadataNormalizer.normalize`` (comparison-only)
  3. Match              -> ``WorkGroupingMatcher.compare`` (scored ``MergeDecision``)
  4. Group              -> ``WorkGrouper.group`` (clusters by score)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Catalogue markers -> canonical marker key. Markers are case-insensitive.
_CATALOGUE_RE = re.compile(
    r"\b(?P<marker>KV|Köchel|Koechel|K\.|K|BWV|Hob\.|Hob|Op\.|Op|D\.|D)"
    r"\s*\.?\s*(?P<num>[0-9]+[A-Za-z]?(?:/[0-9]+[A-Za-z]?)?)\b",
    re.IGNORECASE,
)

# Work number: "No. 16", "No.16", "Number 16".
_NUMBER_RE = re.compile(r"\b(?:No\.?|Number|Nº)\s*(?P<num>[0-9]+[A-Za-z]?)\b", re.IGNORECASE)

# Key: "in C major", "in C", "in A-flat minor", "in F# minor".
_KEY_RE = re.compile(
    r"\bin\s+(?P<key>[A-H](?:-?flat|b|#|sharp)?(?:\s+(?:major|minor|maj|min))?)\b",
    re.IGNORECASE,
)

# Opus: "Op. 67", "opus 67".
_OPUS_RE = re.compile(r"\b(?:Op\.?|Opus)\s*\.?\s*(?P<num>[0-9]+[A-Za-z]?)\b", re.IGNORECASE)

_CATALOGUE_NORMALIZE = {
    "kv": "k",
    "k": "k",
    "köchel": "k",
    "koechel": "k",
    "bwv": "bwv",
    "hob": "hob",
    "d": "d",
    "op": "opus",
}

_CATALOGUE_DISPLAY = {
    "k": "K",
    "bwv": "BWV",
    "hob": "Hob",
    "d": "D",
    "opus": "Op.",
}

_MAJOR_MINOR = re.compile(r"\b(?:major|maj)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ExtractedMetadata:
    """Structured elements parsed from a title. The title itself is untouched."""

    catalogue: str | None = None  # canonical, e.g. "k 128"
    catalogue_raw: str | None = None  # as found, e.g. "K.128"
    work_number: str | None = None  # e.g. "16"
    key: str | None = None  # e.g. "c major"
    opus: str | None = None  # canonical, e.g. "opus 67"

    @property
    def has_any(self) -> bool:
        return any((self.catalogue, self.work_number, self.key, self.opus))


def extract_metadata(title: str) -> ExtractedMetadata:
    """Parse structured elements from a title. Never modifies ``title``."""
    catalogue: str | None = None
    catalogue_raw: str | None = None
    key: str | None = None
    opus: str | None = None

    m = _CATALOGUE_RE.search(title)
    if m:
        marker = m.group("marker").rstrip(".").lower()
        marker_key = _CATALOGUE_NORMALIZE.get(marker, marker)
        num = m.group("num")
        catalogue_raw = f"{m.group('marker')}.{num}"
        catalogue = f"{_CATALOGUE_DISPLAY.get(marker_key, marker_key)} {num}"

    m = _NUMBER_RE.search(title)
    work_number = m.group("num") if m else None

    m = _KEY_RE.search(title)
    if m:
        raw_key = m.group("key")
        key = re.sub(_MAJOR_MINOR, "major", raw_key.lower()).strip()

    m = _OPUS_RE.search(title)
    if m:
        opus = f"opus {m.group('num').lower()}"

    return ExtractedMetadata(
        catalogue=catalogue,
        catalogue_raw=catalogue_raw,
        work_number=work_number,
        key=key,
        opus=opus,
    )
