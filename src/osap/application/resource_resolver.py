"""Resolución de una obra en recursos (partituras, audios) y representaciones.

La unidad que interesa al usuario NO es la representación, sino el RECURSO:
"necesito Ave Verum Corpus" -> partitura MusicXML, partitura PDF, audio.

Modelo:

    Work
      └─ Resource (kind + format + role)      MusicXML · PDF · audio soprano ...
           └─ Representation (provider)        OMR · OpenScore (directa)

La selección se hace POR RECURSO: entre las representaciones de un recurso se
elige la descargable (directa) aunque otra tenga mejor metadata.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.osap.application.acquisition import AcquisitionInfo, AcquisitionMethod, AcquisitionResolver
from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.work_grouper import WorkGroup, _preference_key

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation

# Apellidos de compositores conocidos -> nombre canónico (para el "mejor compositor").
_KNOWN_LAST_NAMES: dict[str, str] = {
    "mozart": "Wolfgang Amadeus Mozart",
    "bach": "Johann Sebastian Bach",
    "beethoven": "Ludwig van Beethoven",
    "schubert": "Franz Schubert",
    "palestrina": "Giovanni Pierluigi da Palestrina",
    "victoria": "Tomás Luis de Victoria",
    "gounod": "Charles Gounod",
    "verdi": "Giuseppe Verdi",
    "brahms": "Johannes Brahms",
    "vivaldi": "Antonio Vivaldi",
    "bruckner": "Anton Bruckner",
    "haendel": "George Frideric Handel",
    "handel": "George Frideric Handel",
    "byrd": "William Byrd",
    "tallis": "Thomas Tallis",
    "monteverdi": "Claudio Monteverdi",
    "rutter": "John Rutter",
}

_AUDIO_FORMATS = {"audio", "youtube", "mp3", "wav", "flac"}


@dataclass(frozen=True)
class Resource:
    """Un recurso concreto de una obra (partitura, audio...)."""

    kind: str  # "score" | "audio"
    format: str  # "musicxml" | "pdf" | ...
    role: str | None  # voz/sección para audio; None para partituras
    representations: tuple[CandidateRepresentation, ...] = field(default_factory=tuple)

    @property
    def best(self) -> CandidateRepresentation | None:
        return self.representations[0] if self.representations else None

    @property
    def downloadable(self) -> bool:
        return any(_direct(r) for r in self.representations)

    @property
    def manual(self) -> bool:
        return bool(self.representations) and not self.downloadable


@dataclass(frozen=True)
class ResolvedWork:
    """Una obra ya resuelta en recursos + representaciones + adquisición."""

    work_id: str
    title: str
    composer: str | None  # mejor compositor disponible (canónico)
    catalog: str | None
    resources: tuple[Resource, ...] = field(default_factory=tuple)
    acquisitions: dict[str, AcquisitionInfo] = field(default_factory=dict)  # candidate_id -> adquisición

    @property
    def has_direct_download(self) -> bool:
        return any(info.method is AcquisitionMethod.DIRECT for info in self.acquisitions.values())

    def acquisition_for(self, rep: CandidateRepresentation) -> AcquisitionInfo | None:
        return self.acquisitions.get(rep.candidate_id.value)


class ResourceResolver:
    """Convierte una obra fusionada (WorkGroup) en recursos resueltos + adquisición."""

    def __init__(self, acquisition_resolver: AcquisitionResolver | None = None) -> None:
        self._acquisition = acquisition_resolver or AcquisitionResolver()

    def resolve(self, group: WorkGroup) -> ResolvedWork:
        buckets: dict[tuple[str, str | None], list[CandidateRepresentation]] = {}
        for rep in group.representations:
            key = (rep.format.value, _role(rep))
            buckets.setdefault(key, []).append(rep)

        resources: list[Resource] = []
        for (fmt, role), reps in buckets.items():
            ordered = sorted(reps, key=_representation_rank)
            resources.append(Resource(kind=_kind(fmt, role), format=fmt, role=role, representations=tuple(ordered)))
        resources.sort(key=_resource_order)

        acquisitions = {rep.candidate_id.value: self._acquisition.resolve(rep) for rep in group.representations}
        return ResolvedWork(
            work_id=group.key,
            title=group.work.title,
            composer=_best_composer(group.representations),
            catalog=group.work.catalogue_number,
            resources=tuple(resources),
            acquisitions=acquisitions,
        )


def _direct(rep: CandidateRepresentation) -> bool:
    return bool(rep.downloadable) and not rep.manual_download


def _representation_rank(rep: CandidateRepresentation) -> tuple[object, ...]:
    """Directa primero, luego manual; dentro, por preferencia de adquisición."""
    return (0 if _direct(rep) else 1, _preference_key(rep))


def _role(rep: CandidateRepresentation) -> str | None:
    # Para partituras el rol es None; para audio futuro, la voz/sección.
    if rep.format.value in _AUDIO_FORMATS:
        notes = str(rep.notes or rep.metadata.get("role") or "")
        return notes.strip().lower() or "general"
    return None


def _kind(fmt: str, role: str | None) -> str:
    return "audio" if (role is not None or fmt in _AUDIO_FORMATS) else "score"


def _resource_order(resource: Resource) -> tuple[int, int, str]:
    score_rank = {"musicxml": 0, "mei": 1, "pdf": 2, "midi": 3}
    kind_rank = 0 if resource.kind == "score" else 1
    fmt_rank = score_rank.get(resource.format, 9) if resource.kind == "score" else 9
    return (kind_rank, fmt_rank, resource.role or "")


def _best_composer(reps: tuple[CandidateRepresentation, ...]) -> str | None:
    """El mejor compositor disponible: preferimos uno conocido (Mozart, ...)."""
    best: str | None = None
    best_score = -1.0
    for rep in reps:
        comp = rep.work_descriptor.composer
        if not comp:
            continue
        score = _composer_quality(comp)
        if score > best_score:
            best = comp
            best_score = score
    if not best:
        return None
    cleaned = _clean_composer(best)
    return MetadataNormalizer.canonical_composer(cleaned) if cleaned else None


def _clean_composer(raw: str) -> str:
    """Si el campo contiene un compositor conocido, extraerlo; si no, limpiarlo."""
    low = raw.lower()
    for last, full in _KNOWN_LAST_NAMES.items():
        if re.search(rf"\b{last}\b", low):
            return full
    # Quitar años y signos, conservar palabras.
    text = re.sub(r"\(?\d{4}[-–]?\d{4}\)?", "", raw)
    return text.strip(" ,-.")


def _composer_quality(comp: str) -> float:
    """Mayor = mejor compositor (conocido > limpio > ruidoso)."""
    low = comp.lower()
    if any(re.search(rf"\b{last}\b", low) for last in _KNOWN_LAST_NAMES):
        return 5.0
    if comp.isascii() and comp.isalpha() or " " in comp and not any(c.isdigit() for c in comp):
        return 2.0
    return 1.0
