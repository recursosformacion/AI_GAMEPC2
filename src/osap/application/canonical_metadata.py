from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.osap.application.metadata_normalizer import MetadataNormalizer

if TYPE_CHECKING:
    from src.osap.application.work_merge_service import WorkGroup
    from src.osap.domain.candidate_representation import CandidateRepresentation

_GENRE_MAP: dict[str, str] = {
    "mass": "Mass",
    "missa": "Mass",
    "messe": "Mass",
    "motet": "Motet",
    "motete": "Motet",
    "anthem": "Anthem",
    "hymn": "Hymn",
    "hymne": "Hymn",
    "chorale": "Chorale",
    "choral": "Choral",
    "symphony": "Symphony",
    "sinfonie": "Symphony",
    "concerto": "Concerto",
    "sonata": "Sonata",
    "nocturne": "Nocturne",
    "song": "Song",
    "lied": "Lied",
    "opera": "Opera",
    "requiem": "Requiem",
    "cantata": "Cantata",
    "overture": "Overture",
}

_VOICE_PATTERNS = [
    ("SATB", re.compile(r"SATB", re.IGNORECASE)),
    ("SSA", re.compile(r"\bSSA\b", re.IGNORECASE)),
    ("TTBB", re.compile(r"TTBB", re.IGNORECASE)),
    ("TTB", re.compile(r"\bTTB\b", re.IGNORECASE)),
    ("SAB", re.compile(r"\bSAB\b", re.IGNORECASE)),
    ("SSAATTBB", re.compile(r"SSAATTBB", re.IGNORECASE)),
]


@dataclass(frozen=True)
class CanonicalComposer:
    composer_id: str
    display_name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CanonicalRepresentation:
    provider: str
    format: str
    downloadable: bool
    quality: str


@dataclass(frozen=True)
class CanonicalWork:
    """The canonical, provider-independent view of a musical work.

    OSAP fills missing fields from the other representations of the same work,
    so the user never sees partial metadata.
    """

    work_id: str
    title: str
    display_title: str | None = None
    canonical_title: str | None = None
    canonical_key: str | None = None
    subtitle: str | None = None
    catalog: str | None = None
    composer: CanonicalComposer | None = None
    creation_year: int | None = None
    genre: str | None = None
    instrumentation: str | None = None
    voices: tuple[str, ...] = field(default_factory=tuple)
    movements: int | None = None
    duration: float | None = None
    language: str | None = None
    license: str | None = None
    public_domain: bool | None = None
    difficulty: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    representations: tuple[CanonicalRepresentation, ...] = field(default_factory=tuple)


class MetadataEnricher:
    """Builds a `CanonicalWork` from a merged `WorkGroup`, merging the fields
    each provider contributes and normalizing musical metadata."""

    def enrich(self, group: WorkGroup) -> CanonicalWork:
        work = group.work
        reps = group.representations
        _, meta = MetadataNormalizer.clean_title(work.title, work.composer)

        composer = _canonical_composer(work.composer) if work.composer else None
        genres = {g for c in reps for g in _genres(c)}
        voices = _voices(reps)
        duration = _first_number(reps, "duration_seconds")

        return CanonicalWork(
            work_id=group.key,
            title=work.title,
            display_title=work.title,
            canonical_title=work.canonical_title,
            canonical_key=work.canonical_key or group.key,
            catalog=meta.get("catalogue") or _catalog_from_reps(reps),
            composer=composer,
            creation_year=_first_int(reps, "creation_year"),
            genre=next((g for g in sorted(genres) if g), None),
            instrumentation=_first_str(reps, "instrumentation"),
            voices=voices,
            movements=None,
            duration=duration,
            language=work.language,
            license=_license(reps),
            public_domain=_public_domain(reps),
            representations=tuple(_canonical_representation(c) for c in reps),
        )


def _canonical_composer(raw: str) -> CanonicalComposer:
    display = MetadataNormalizer.canonical_composer(raw)
    composer_id = "c" + re.sub(r"[^a-z0-9]", "", MetadataNormalizer.canonical_composer(raw).lower())
    return CanonicalComposer(composer_id=composer_id, display_name=display, aliases=(raw,))


def _genres(candidate: CandidateRepresentation) -> list[str]:
    raw = candidate.metadata.get("genres")
    if not raw:
        return []
    parts = re.split(r"[,;/]|\b(?:and|&)\b", str(raw), flags=re.IGNORECASE)
    return [normalize_genre(p.strip()) for p in parts if p.strip()]


def normalize_genre(raw: str) -> str:
    key = raw.strip().lower()
    return _GENRE_MAP.get(key, raw.strip().title())


def _voices(candidates: tuple[CandidateRepresentation, ...]) -> tuple[str, ...]:
    found: set[str] = set()
    for candidate in candidates:
        for label, pattern in _VOICE_PATTERNS:
            if pattern.search(
                str(candidate.metadata.get("voices") or "") + " " + str(candidate.work_descriptor.instrumentation or "")
            ):
                found.add(label)
    return tuple(sorted(found))


def _first(candidates: tuple[CandidateRepresentation, ...], key: str) -> str | None:
    for candidate in candidates:
        value = candidate.metadata.get(key)
        if value:
            return str(value)
    return None


def _first_str(candidates: tuple[CandidateRepresentation, ...], key: str) -> str | None:
    return _first(candidates, key)


def _first_number(candidates: tuple[CandidateRepresentation, ...], key: str) -> float | None:
    for candidate in candidates:
        value = candidate.metadata.get(key)
        try:
            return float(str(value))
        except (TypeError, ValueError):
            continue
    return None


def _first_int(candidates: tuple[CandidateRepresentation, ...], key: str) -> int | None:
    value = _first_number(candidates, key)
    return int(value) if value is not None else None


def _catalog_from_reps(candidates: tuple[CandidateRepresentation, ...]) -> str | None:
    for candidate in candidates:
        raw = str(candidate.metadata.get("catalogue") or "")
        if raw:
            return raw
        _, meta = MetadataNormalizer.clean_title(candidate.work_descriptor.title, candidate.work_descriptor.composer)
        if meta.get("catalogue"):
            return str(meta["catalogue"])
    return None


def _license(candidates: tuple[CandidateRepresentation, ...]) -> str | None:
    if any(c.public_domain is True for c in candidates):
        return "Dominio público"
    for candidate in candidates:
        if candidate.license:
            return str(candidate.license)
    return None


def _public_domain(candidates: tuple[CandidateRepresentation, ...]) -> bool | None:
    """Tri-state public domain aggregation.

    Returns ``True`` if any representation is known public domain, ``False``
    if at least one is known non-public (and none public), and ``None``
    (unknown) when no representation carries information.
    """
    if any(c.public_domain is True for c in candidates):
        return True
    if any(c.public_domain is False for c in candidates):
        return False
    return None


def _canonical_representation(candidate: CandidateRepresentation) -> CanonicalRepresentation:
    return CanonicalRepresentation(
        provider=candidate.provider_id.value,
        format=candidate.format.value,
        downloadable=bool(candidate.metadata.get("downloadable", True)),
        quality=candidate.quality.name,
    )
