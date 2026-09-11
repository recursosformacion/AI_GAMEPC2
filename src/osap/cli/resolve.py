"""CLI: resolve (F5.6)."""

import argparse

from src.osap.application.work_resolution_engine import ProviderReport
from src.osap.bootstrap.container import Container
from src.osap.cli.requests import _build_request, _choose_work_then_repr, _ordered_candidates, _representations_for
from src.osap.cli.ui import _print_result, _print_summary
from src.osap.domain.errors import ScoreResolutionError


def _run_resolve(args: argparse.Namespace, container: Container) -> int:
    if not args.query and not args.composer:
        print("Indica un título o un --composer.")
        return 2
    request = _build_request(args, args.query)
    engine = container.work_resolution_engine()
    print("Searching providers...")
    print("-" * 40)
    reports = engine.provider_status(request, on_progress=_progress)
    for report in reports:
        print(f"{report.provider_id.value:<16} {_outcome(report)}")
    print("-" * 40)
    try:
        ranked = _ordered_candidates(engine, request, on_progress=_progress)
    except ScoreResolutionError as exc:
        print(f"Error: {exc}")
        return 1
    if not ranked:
        print(f"\nNo se encontraron obras para '{request.query or request.title or request.composer}'.")
        return 1

    groups = container.work_merge_service().group(ranked)
    _print_summary(ranked, groups, reports)

    if args.index is not None:
        chosen_idx = args.index
        all_candidates = list(ranked)
        if chosen_idx >= len(all_candidates):
            chosen_idx = 0
        best = all_candidates[chosen_idx]
    else:
        best = _choose_work_then_repr(groups, ranked)
        if best is None:
            return 1

    print("Seleccionando representación...")
    result = engine.resolve(
        request,
        download=True,
        representations=_representations_for(ranked, groups, best),
        on_progress=_progress,
    )
    if result.chosen is None:
        print("No se pudo descargar la representación elegida.")
        for diag in result.diagnostics:
            print(f"  - {diag}")
        return 1
    _print_result(result)
    return 0


def _outcome(report: ProviderReport) -> str:
    labels = {
        "ok": "OK",
        "no_result": "NO RESULT",
        "unavailable": "UNAVAILABLE",
        "error": "ERROR",
    }
    text = labels.get(report.outcome, report.outcome.upper())
    detail = report.detail
    return f"{text} {detail}".strip()


def _progress(message: str) -> None:
    print(f"  · {message}", flush=True)

