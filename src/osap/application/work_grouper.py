"""Grouping of representations into distinct works via scored matching."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.metadata_parser import extract_metadata
from src.osap.application.representation_identity import build_identity
from src.osap.application.work_grouping_matcher import WorkGroupingMatcher, _composer_signal
from src.osap.domain.normalization import stable_id
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.domain.work_group import WorkGroup

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


def _block_keys(candidate: CandidateRepresentation) -> tuple[tuple[str, str, str], ...]:
    """Claves de bloqueo: condiciones NECESARIAS para que el matcher fusione.

    - ("cat", "", catálogo): la regla fuerte exige catálogo igual (independiente del
      compositor: también fusiona "específico + sin dato" con catálogo común).
    - ("num", grupo, número): la regla compositor+número+clave exige mismo número.
    - ("bi", grupo, "tok1|tok2") o ("tok", grupo, token): el fallback por título exige
      Jaccard ≥ 0.6, lo que con ≥2 tokens implica ≥2 tokens en común (⇒ comparten un
      bigrama); con 1 token, comparten ese token. El grupo de compositor separa
      "específico" de "sin dato/anónimo" (veto 1/2 del matcher).
    """
    identity = build_identity(candidate.work_descriptor.title, candidate.work_descriptor.composer)
    category, key = _composer_signal(candidate.work_descriptor.composer)
    group = key if category == "specific" else "nonspecific"
    keys: list[tuple[str, str, str]] = []
    if identity.catalog:
        keys.append(("cat", "", identity.catalog))
    if identity.work_number:
        keys.append(("num", group, identity.work_number))
    tokens = sorted({token for token in (identity.title or "").split() if token})
    if len(tokens) == 1:
        keys.append(("tok", group, tokens[0]))
    elif len(tokens) >= 2:
        for i, first in enumerate(tokens):
            for second in tokens[i + 1 :]:
                keys.append(("bi", group, f"{first}|{second}"))
    return tuple(keys)


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
        """Agrupa por similitud, con **bloqueo por claves necesarias** para no ser O(n²).

        El matcher decide por igualdades/vetos: para fusionar hacen falta (a) mismo
        catálogo, o (b) mismo número de obra, o (c) solape de tokens del título ≥0.6.
        Por tanto solo pueden fusionarse candidatos que comparten alguna de esas claves;
        se indexan las clusters por ellas y solo se compara con las que comparten bloque.
        El resultado es idéntico al de comparar contra todas (ver test de equivalencia).
        """
        ordered = sorted(candidates, key=_sort_key)
        clusters: list[list[CandidateRepresentation]] = []
        buckets: dict[tuple[str, str, str], list[int]] = {}

        for candidate in ordered:
            keys = _block_keys(candidate)
            seen: set[int] = set()
            for key in keys:
                for index in buckets.get(key, ()):
                    seen.add(index)
            best_index: int | None = None
            best_score = self._matcher.threshold
            for index in sorted(seen):  # orden ascendente: mismo desempate que el bucle completo
                decision = self._matcher.compare(candidate, clusters[index][0])
                if decision.score >= best_score:
                    best_index = index
                    best_score = decision.score
            if best_index is None:
                clusters.append([candidate])
                index = len(clusters) - 1
            else:
                clusters[best_index].append(candidate)
                index = best_index
            for key in keys:
                buckets.setdefault(key, []).append(index)

        groups: list[WorkGroup] = []
        for cluster in clusters:
            work = self._canonical(cluster)
            groups.append(
                WorkGroup(
                    work=work,
                    representations=tuple(cluster),
                    providers=tuple(sorted({r.provider_id for r in cluster}, key=lambda p: p.value)),
                )
            )
        groups.sort(key=lambda g: (-len(g.representations), g.work.title.lower()))
        return tuple(groups)

    def group_reference(
        self, candidates: tuple[CandidateRepresentation, ...]
    ) -> tuple[WorkGroup, ...]:
        """Implementación de referencia O(n²) (sin bloqueo). Solo para tests."""
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
            groups.append(
                WorkGroup(
                    work=self._canonical(cluster),
                    representations=tuple(cluster),
                    providers=tuple(sorted({r.provider_id for r in cluster}, key=lambda p: p.value)),
                )
            )
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
        display = self._normalizer.clean_display_title(title, composer, keep_catalogue=True)

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
            work_id=WorkId(f"work-{stable_id(signature)}"),
            title=display,
            composer=comp_norm,
            catalogue_number=catalogue,
            key=mkey,
            opus=opus,
            canonical_title=core,
            canonical_key=signature,
        )
