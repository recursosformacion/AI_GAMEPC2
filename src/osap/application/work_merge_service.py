from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation

_FORMAT_WEIGHT = {
    OutputFormat.MUSICXML: 3.0,
    OutputFormat.MEI: 2.0,
    OutputFormat.SCORE: 2.0,
    OutputFormat.PDF: 1.0,
    OutputFormat.MIDI: 1.0,
}


def _representation_score(candidate: CandidateRepresentation) -> float:
    """A heuristic 'canonical' score: downloadable, structured format, confidence,
    public domain, and provider rating all contribute."""
    score = 0.0
    if candidate.metadata.get("downloadable", True):
        score += 5.0
    score += _FORMAT_WEIGHT.get(candidate.format, 0.0)
    score += min(float(candidate.confidence.value), 1.0) * 2.0
    if candidate.public_domain is True:
        score += 1.0
    rating = candidate.metadata.get("rating")
    with contextlib.suppress(TypeError, ValueError):
        score += min(float(str(rating)) / 5.0, 1.0)
    return score


class WorkMergeService:
    """Groups equivalent CandidateRepresentations into distinct works.

    Representations that share a normalized identity (composer + clean title)
    are merged under a single `WorkDescriptor`. Each group exposes a
    `canonical_score` and a `primary` representation (best available).
    """

    def __init__(self) -> None:
        self._normalizer = MetadataNormalizer()

    def group(self, candidates: tuple[CandidateRepresentation, ...]) -> tuple[WorkGroup, ...]:
        buckets: dict[str, list[CandidateRepresentation]] = {}
        for candidate in candidates:
            work = candidate.work_descriptor
            key = self._normalizer.work_key(work.title, work.composer)
            buckets.setdefault(key, []).append(candidate)
        groups: list[WorkGroup] = []
        for key, members in buckets.items():
            groups.append(WorkGroup(key=key, work=self._canonical(members), representations=tuple(members)))
        groups.sort(key=lambda g: (-len(g.representations), g.work.title.lower()))
        return tuple(groups)

    def _canonical(self, members: list[CandidateRepresentation]) -> WorkDescriptor:
        """Build the merged work.

        The display title is the *best available raw title* across the member
        representations (longest non-empty wins); it is never the output of the
        normalizer. The normalizer runs only to produce the internal
        ``canonical_title`` and ``canonical_key`` used for grouping/comparison.
        """
        first = members[0].work_descriptor
        title = first.title
        composer = first.composer
        for m in members:
            if len(m.work_descriptor.title) > len(title):
                title = m.work_descriptor.title
            if not composer and m.work_descriptor.composer:
                composer = m.work_descriptor.composer
        key = self._normalizer.work_key(title, composer)
        clean_title, _meta = self._normalizer.clean_title(title, composer)
        return WorkDescriptor(
            work_id=WorkId(f"work-{abs(hash(key))}"),
            title=title,
            canonical_title=clean_title,
            canonical_key=key,
            composer=self._normalizer.canonical_composer(composer) if composer else None,
        )


class WorkGroup:
    """A merged work with all its equivalent representations."""

    __slots__ = ("key", "work", "representations", "primary", "canonical_score")

    def __init__(
        self,
        key: str,
        work: WorkDescriptor,
        representations: tuple[CandidateRepresentation, ...],
    ) -> None:
        self.key = key
        self.work = work
        self.representations = tuple(sorted(representations, key=_representation_score, reverse=True))
        self.primary = self.representations[0] if self.representations else None
        self.canonical_score = _representation_score(self.primary) if self.primary is not None else 0.0
