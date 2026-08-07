"""Grouping of representations into distinct works via scored matching."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.metadata_parser import extract_metadata
from src.osap.application.work_grouping_matcher import WorkGroupingMatcher
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation


# Preferred acquisition order (lowest value = best).
def _preference_key(candidate: CandidateRepresentation) -> tuple[int, ...]:
    fmt = candidate.format
    provider = candidate.provider_id.value
    downloadable = candidate.downloadable
    if provider == "local":
        if fmt is OutputFormat.MUSICXML:
            return (0,)
        if fmt is OutputFormat.MEI:
            return (1,)
        if fmt is OutputFormat.SCORE:
            return (2,)
        return (3,)
    if provider == "openscore" and fmt is OutputFormat.MUSICXML:
        return (5,)
    if fmt is OutputFormat.MUSICXML and downloadable:
        return (6,)
    if fmt is OutputFormat.MUSICXML:
        return (7,)
    if downloadable:
        return (8,)
    return (9,)


def _sort_key(candidate: CandidateRepresentation) -> tuple[object, ...]:
    return (_preference_key(candidate), -candidate.confidence.value, candidate.provider_id.value)


class WorkGrouper:
    """Groups representations into works using scored matching.

    Two representations merge when their ``MergeDecision.score`` reaches the
    matcher's threshold. This is a generic, reusable algorithm (no per-work
    heuristics) and can later use an AI/hybrid matcher without changing the
    grouping logic.
    """

    def __init__(self, matcher: WorkGroupingMatcher | None = None) -> None:
        self._matcher = matcher or WorkGroupingMatcher()
        self._normalizer = MetadataNormalizer()

    def group(self, candidates: tuple[CandidateRepresentation, ...]) -> tuple[WorkGroup, ...]:
        ordered = sorted(candidates, key=_sort_key)
        clusters: list[list[CandidateRepresentation]] = []
        for candidate in ordered:
            best_index: int | None = None
            best_score = self._matcher.threshold
            for index, cluster in enumerate(clusters):
                decision = self._matcher.compare(candidate, cluster[0])
                if decision.score >= best_score:
                    best_index = index
                    best_score = decision.score
            if best_index is None:
                clusters.append([candidate])
            else:
                clusters[best_index].append(candidate)

        groups: list[WorkGroup] = []
        for cluster in clusters:
            work = self._canonical(cluster)
            groups.append(WorkGroup(key=work.canonical_key or "", work=work, representations=tuple(cluster)))
        groups.sort(key=lambda g: (-len(g.representations), g.work.title.lower()))
        return tuple(groups)

    def _canonical(self, members: list[CandidateRepresentation]) -> WorkDescriptor:
        """Build the merged work.

        The display title is the clean display title of the best-preference
        representation; catalogue/number/key/opus are aggregated from any member
        and stored separately. The stable id comes from a normalized signature
        (used only for identity, NOT for merging).
        """
        best = min(members, key=_sort_key)
        title = best.work_descriptor.title
        composer = best.work_descriptor.composer
        for m in members:
            if not composer and m.work_descriptor.composer:
                composer = m.work_descriptor.composer
        display = self._normalizer.clean_display_title(title, composer)

        catalogue: str | None = None
        mkey: str | None = None
        number: str | None = None
        opus: str | None = None
        for m in members:
            me = extract_metadata(m.work_descriptor.title)
            if me.catalogue and not catalogue:
                catalogue = me.catalogue
            if me.key and not mkey:
                mkey = me.key
            if me.work_number and not number:
                number = me.work_number
            if me.opus and not opus:
                opus = me.opus

        comp_norm = self._normalizer.canonical_composer(composer) if composer else None
        core = self._normalizer.comparison_title(title, composer)
        signature = self._normalizer.normalize(title, composer).signature()

        return WorkDescriptor(
            work_id=WorkId(f"work-{abs(hash(signature))}"),
            title=display,
            composer=comp_norm,
            catalogue_number=catalogue,
            key=mkey,
            opus=opus,
            canonical_title=core,
            canonical_key=signature,
        )


class WorkGroup:
    """A merged work with ALL its equivalent representations preserved."""

    __slots__ = ("key", "work", "representations", "primary", "canonical_score")

    def __init__(
        self,
        key: str,
        work: WorkDescriptor,
        representations: tuple[CandidateRepresentation, ...],
    ) -> None:
        self.key = key
        self.work = work
        self.representations = tuple(sorted(representations, key=_sort_key))
        self.primary = self.representations[0] if self.representations else None
        self.canonical_score = -_preference_key(self.primary)[0] if self.primary is not None else 0.0
