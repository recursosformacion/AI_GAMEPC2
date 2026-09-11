"""CLI: requests (F5.6)."""

import argparse
from collections.abc import Callable

from src.osap.application.ranker import DefaultWorkRanker
from src.osap.application.work_grouper import WorkGrouper
from src.osap.application.work_merge_service import _sort_key
from src.osap.cli.ui import _print_candidate, _print_work_detail, _prompt_index, _safe, _work_list_line
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.ranking import RankingContext, RankingPolicy, UserPreferences
from src.osap.domain.resolve_request import ResolveRequest, ResolveRequestBuilder
from src.osap.domain.value_objects import WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

ProgressCallback = Callable[[str], None]


def _ordered_candidates(
    engine: object,
    request: ResolveRequest,
    on_progress: ProgressCallback | None = None,
) -> tuple[CandidateRepresentation, ...]:
    """Candidatos en orden V2.1: agrupa en obras → rankea obras → aplana por preferencia.

    Sustituye al ranking V1 del CLI (F4.E): representaciones → evidencia → obra → orden.
    """
    gathered = engine.gather(request, on_progress=on_progress)  # type: ignore[attr-defined]
    groups = WorkGrouper().group(gathered.candidates)
    descriptor = WorkDescriptor(
        work_id=WorkId("cli"),
        title=(request.title or request.query or " "),
        composer=request.composer,
    )
    ranking = DefaultWorkRanker().rank(
        groups,
        RankingContext(query_descriptor=descriptor, user_preferences=UserPreferences()),
        RankingPolicy(),
    )
    ordered: list[CandidateRepresentation] = []
    for score in ranking.order:
        ordered.extend(sorted(score.work.representations, key=_sort_key))
    return tuple(ordered)


def _parse_format(value: str) -> OutputFormat:
    normalized = value.lower()
    for fmt in OutputFormat:
        if fmt.value == normalized:
            return fmt
    choices = ", ".join(fmt.value for fmt in OutputFormat)
    raise argparse.ArgumentTypeError(f"unknown format '{value}' (choose from: {choices})")


def _build_request(args: argparse.Namespace, query: str | None) -> ResolveRequest:
    builder = ResolveRequestBuilder()
    if query:
        builder = builder.text(query)
    if getattr(args, "composer", None):
        builder = builder.composer(args.composer)
    if getattr(args, "genre", None):
        builder = builder.genre(args.genre)
    if getattr(args, "language", None):
        builder = builder.language(args.language)
    if getattr(args, "voices", None):
        builder = builder.voices(*args.voices)
    if getattr(args, "output_format", None):
        builder = builder.format(args.output_format)
    return builder.build()


def _choose_candidate(candidates: tuple[CandidateRepresentation, ...], index: int | None) -> int:
    if len(candidates) == 1:
        return 0
    if index is not None and index < len(candidates):
        return index
    print(f"Se encontraron {len(candidates)} versiones. Elige una:")
    for i, candidate in enumerate(candidates):
        _print_candidate(i, candidate, recommend=False)
    while True:
        raw = input(f"Índice [0-{len(candidates) - 1}]: ")
        try:
            choice = int(raw)
            if 0 <= choice < len(candidates):
                return choice
        except ValueError:
            pass
        print("Índice no válido.")


def _choose_work_then_repr(
    groups: tuple[object, ...], ranked: tuple[CandidateRepresentation, ...]
) -> CandidateRepresentation | None:
    from src.osap.application.work_merge_service import WorkGroup

    if not groups:
        return None
    print(f"\n{len(groups)} obra(s) encontrada(s):")
    for index, group in enumerate(groups):
        if not isinstance(group, WorkGroup):
            continue
        print(_work_list_line(index, group))

    work_idx = _prompt_index(len(groups), "obra")
    if work_idx is None:
        return None
    group = groups[work_idx]
    if not isinstance(group, WorkGroup):
        return None

    _print_work_detail(group)

    if len(group.representations) == 1:
        return group.representations[0]

    print(f"\n  Representaciones para '{_safe(group.work.title)}':")
    for i, c in enumerate(group.representations):
        _print_candidate(i, c, recommend=bool(i == 0))

    repr_idx = _prompt_index(len(group.representations), "representacion")
    return group.representations[repr_idx] if repr_idx is not None else None


def _representations_for(
    ranked: tuple[CandidateRepresentation, ...], groups: tuple[object, ...], target: CandidateRepresentation
) -> tuple[CandidateRepresentation, ...]:
    """Return the representations of the work the user selected.

    Resolution is scoped to the selected work only, so it never re-scans
    unrelated providers/works for download.
    """
    from src.osap.application.work_merge_service import WorkGroup

    for group in groups:
        if not isinstance(group, WorkGroup):
            continue
        if any(r.candidate_id == target.candidate_id for r in group.representations):
            return group.representations
    return tuple(c for c in ranked if c.candidate_id == target.candidate_id)

