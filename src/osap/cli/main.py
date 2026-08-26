import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path

from src.osap.application.work_resolution_engine import ProviderReport
from src.osap.bootstrap.configuration import load_configuration
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.errors import ScoreResolutionError
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest, ResolveRequestBuilder
from src.osap.domain.resolve_result import ResolveResult
from src.osap.domain.value_objects import CatalogId


def _parse_format(value: str) -> OutputFormat:
    normalized = value.lower()
    for fmt in OutputFormat:
        if fmt.value == normalized:
            return fmt
    choices = ", ".join(fmt.value for fmt in OutputFormat)
    raise argparse.ArgumentTypeError(f"unknown format '{value}' (choose from: {choices})")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="osap", description="OSAP — resolución de obras musicales.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser("resolve", help="Resuelve y descarga una obra musical.")
    resolve.add_argument("query", nargs="?", default=None, help="Título o texto libre (opcional si se usa --composer).")
    resolve.add_argument("--composer", default=None)
    resolve.add_argument("--genre", default=None)
    resolve.add_argument("--language", default=None)
    resolve.add_argument("--voices", nargs="*", default=[])
    resolve.add_argument("--format", dest="output_format", type=_parse_format, default=None)
    resolve.add_argument("--index", type=int, default=None, help="Índice del candidato (evita el prompt).")
    resolve.add_argument("--library", default=None)

    download = subparsers.add_parser("download", help="Descarga un candidato concreto de una obra.")
    download.add_argument("query", nargs="?", default=None)
    download.add_argument("--composer", default=None)
    download.add_argument("--format", dest="output_format", type=_parse_format, default=OutputFormat.MUSICXML)
    download.add_argument("--index", type=int, default=None)
    download.add_argument("--library", default=None)

    catalog = subparsers.add_parser("catalog", help="Lista catálogos musicales.")
    catalog_sub = catalog.add_subparsers(dest="catalog_command", required=True)

    validate = subparsers.add_parser("validate", help="Valida un MusicXML/.mxl y muestra su calidad.")
    validate.add_argument("path", help="Ruta al fichero MusicXML (.xml/.musicxml) o .mxl")
    validate.add_argument("--title", default=None, help="Título (opcional, va al Score)")
    validate.add_argument("--composer", default=None, help="Compositor (opcional, va al Score)")
    catalog_sub.add_parser("list", help="Lista catálogos disponibles.")
    catalog_sub.add_parser("info", help="Información de un catálogo.").add_argument("name")

    search = subparsers.add_parser("search", help="Busca obras musicales (tolerante).")
    search.add_argument("query", nargs="?", default=None)
    search.add_argument(
        "--composer",
        nargs="?",
        const="__QUERY__",
        default=None,
        help="Compositor (o flag: usa el término como compositor).",
    )
    search.add_argument("--works", action="store_true", help="Trata el término como compositor y lista sus obras.")
    search.add_argument("--all", action="store_true", help="Busca en todos los catálogos.")
    search.add_argument("--format", dest="output_format", type=_parse_format, default=None)

    return parser


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
        ranked = engine.rank(request, on_progress=_progress)
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


def _print_summary(
    ranked: tuple[CandidateRepresentation, ...],
    groups: tuple[object, ...],
    reports: tuple[ProviderReport, ...] = (),
) -> None:
    from src.osap.application.work_merge_service import WorkGroup

    n_results = len(ranked)
    n_works = len(groups)
    n_reps = sum(len(g.representations) for g in groups if isinstance(g, WorkGroup))
    print(f"{n_results} resultados encontrados")
    print(f"{n_works} obras distintas")
    print(f"{n_reps} representaciones")
    print("Representaciones encontradas")
    for report in reports:
        pid = report.provider_id.value
        count = sum(1 for c in ranked if c.provider_id.value == pid)
        print(f"  {pid:<12} {count:<4} {_status_note(report)}")
    print()


def _status_note(report: ProviderReport) -> str:
    detail = report.detail
    if report.outcome == "ok":
        return ""
    if report.outcome == "no_result":
        return "(sin resultados)"
    if report.outcome == "error":
        return "(error)"
    notes = {
        "index_missing": "(índice no disponible)",
        "index_building": "(índice construyéndose)",
        "index_available": "",
        "mirror_not_configured": "(mirror no configurado)",
        "download_unsupported": "(descarga individual no soportada)",
        "network_error": "(error de red)",
    }
    return notes.get(detail, "(no disponible)")


def _work_list_line(index: int, group: object) -> str:
    from src.osap.application.work_merge_service import WorkGroup

    if not isinstance(group, WorkGroup):
        return ""
    composer = _safe(group.work.composer or "")
    formats = "/".join(sorted({c.format.value for c in group.representations}))
    providers = "+".join(sorted({c.provider_id.value for c in group.representations}))
    pd = "PD" if any(c.public_domain is True for c in group.representations) else ""
    catalogue = f" [{_safe(group.work.catalogue_number)}]" if group.work.catalogue_number else ""
    line = f"  [{index}] {_safe(group.work.title)}"
    if composer:
        line += f" -- {_safe(composer)}"
    line += catalogue
    line += f"\n          {formats} · {providers}"
    if pd:
        line += f" · {pd}"
    return line


def _print_work_detail(group: object) -> None:
    from src.osap.application.canonical_metadata import MetadataEnricher
    from src.osap.application.work_merge_service import WorkGroup

    if not isinstance(group, WorkGroup):
        return
    cw = MetadataEnricher().enrich(group)
    print(f"\n  {_safe(cw.title)}")
    if cw.catalog:
        print(f"     Catálogo: {_safe(cw.catalog)}")
    if cw.composer:
        print(f"     Compositor: {_safe(cw.composer.display_name)}")
    if cw.genre:
        print(f"     Género: {_safe(cw.genre)}")
    if cw.creation_year:
        print(f"     Año: {cw.creation_year}")
    if cw.voices:
        print(f"     Voces: {'+'.join(cw.voices)}")
    if cw.instrumentation:
        print(f"     Instrumentación: {_safe(cw.instrumentation)}")
    if cw.language:
        print(f"     Idioma: {_safe(cw.language)}")
    if cw.duration:
        print(f"     Duración: {cw.duration:.1f} s")
    print(f"     Dominio público: {_public_domain_label(cw.public_domain)}")
    print("     Representaciones:")
    for r in cw.representations:
        status = "✓" if r.downloadable else "⚠"
        line = f"        {status} {r.provider:<10} {r.format}"
        if r.manual_download or not r.downloadable:
            if r.download_url:
                line += f"  → Abrir: {r.download_url}"
            else:
                line += "  → descarga manual requerida"
        print(line)


def _prompt_index(count: int, label: str) -> int | None:
    if count == 1:
        return 0
    while True:
        raw = input(f"Indice de {label} [0-{count - 1}] (Enter=0): ").strip()
        if not raw:
            return 0
        try:
            choice = int(raw)
            if 0 <= choice < count:
                return choice
        except ValueError:
            pass
        print("Indice no valido.")


def _index_of(ranked: tuple[CandidateRepresentation, ...], target: CandidateRepresentation) -> int:
    for i, c in enumerate(ranked):
        if c.candidate_id == target.candidate_id:
            return i
    return 0


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


def _print_result(result: ResolveResult) -> None:
    chosen = result.chosen
    if chosen is None:
        print("No se pudo resolver.")
        return
    if result.local_path and result.score_id:
        print(f"\nDescargado {chosen.format.value.upper()} desde {chosen.provider_id.value}.")
        for diag in result.diagnostics:
            print(f"  - {diag}")
        print("\nParsing MusicXML...")
        print("Validando...")
        print("Score creado.")
        print(f"Score Id: {result.score_id}")
        print(f"Guardado en biblioteca: {result.local_path}")
    elif result.local_path:
        print(f"\nDescargado {chosen.format.value.upper()} desde {chosen.provider_id.value}.")
        for diag in result.diagnostics:
            print(f"  - {diag}")
        print(f"\nGuardado en biblioteca (sin Score estructurado): {result.local_path}")
    elif chosen.manual_download or not chosen.downloadable:
        print(f"\n⚠ Descarga manual requerida: {chosen.provider_id.value}")
        if chosen.download_url:
            print(f"   Abrir: {chosen.download_url}")
        if chosen.notes:
            print(f"   Motivo: {chosen.notes}")
        for diag in result.diagnostics:
            print(f"  - {diag}")
    else:
        for diag in result.diagnostics:
            print(f"  - {diag}")
        print("\nNo se pudo descargar ninguna representación automáticamente.")
    print("Resolución terminada.")


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


def _public_domain_label(value: bool | None) -> str:
    if value is True:
        return "Sí"
    if value is False:
        return "No"
    return "Desconocido"


def _safe(text: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


def _print_candidate(index: int, candidate: CandidateRepresentation, recommend: bool) -> None:
    title = _safe(candidate.work_descriptor.title)
    composer = _safe(candidate.work_descriptor.composer or "")
    label = f"  [{index}] {title}"
    if composer:
        label += f" -- {composer}"
    label += f" ({candidate.provider_id.value} - {candidate.format.value}"
    if candidate.public_domain is True:
        label += " - PD"
    label += ")"
    if recommend:
        label += " ***"
    print(label)
    files = candidate.metadata.get("file_list")
    if isinstance(files, (list, tuple)):
        files = [str(f) for f in files if isinstance(f, str)]
        max_show = 3
        for sub in files[:max_show]:
            print(f"       |-- {sub}")
        if len(files) > max_show:
            print(f"       |-- ... y {len(files) - max_show} mas")


def _print_best_source(candidate: CandidateRepresentation) -> None:
    print("\nBest source:")
    print("=" * 40)
    print(f"Title      : {candidate.work_descriptor.title}")
    print(f"Provider   : {candidate.provider_id.value}")
    print(f"Format     : {candidate.format.value}")
    print(f"Quality    : {candidate.quality.name.replace('_', ' ').title()}")
    print(f"License    : {candidate.license or 'desconocida'}")
    print(f"Confidence : {candidate.confidence.value:.2f}")
    print("=" * 40)


def _run_download(args: argparse.Namespace, container: Container) -> int:
    if not args.query and not args.composer:
        print("Indica un título o un --composer.")
        return 2
    request = _build_request(args, args.query)
    engine = container.work_resolution_engine()
    print("Searching providers...")
    try:
        ranked = engine.rank(request, on_progress=_progress)
    except ScoreResolutionError as exc:
        print(f"Error: {exc}")
        return 1
    if not ranked:
        print(f"No se encontraron representaciones para '{request.query or request.title or request.composer}'.")
        return 1
    chosen_index = _choose_candidate(ranked, args.index)
    best = ranked[chosen_index]
    print("Seleccionando representación...")
    result = engine.resolve(
        request,
        download=True,
        representations=_representations_for(ranked, container.work_merge_service().group(ranked), best),
        on_progress=_progress,
    )
    if result.chosen is None or result.local_path is None:
        print("No se pudo descargar el candidato.")
        for diag in result.diagnostics:
            print(f"  - {diag}")
        return 1
    print(f"Descargado: {result.chosen.work_descriptor.title} ({result.chosen.format.value})")
    print(f"  guardado en biblioteca: {result.local_path}")
    return 0


def _run_catalog(args: argparse.Namespace, container: Container) -> int:
    manager = container.catalog_manager()
    try:
        if args.catalog_command == "list":
            catalogs = manager.list()
            if not catalogs:
                print("No hay catálogos.")
                return 1
            for catalog_id in catalogs:
                print(f"  {catalog_id.value}")
            return 0
        if args.catalog_command == "info":
            from src.osap.application.capabilities_dto import CapabilitiesDto

            info = manager.info(CatalogId(args.name))
            caps = manager.capabilities(CatalogId(args.name))
            print(f"catálogo: {info.name} ({info.provider_id.value})")
            dto = CapabilitiesDto.build(info.provider_id.value, caps, available=True, authenticated=False)
            for key, value in dto.items():
                print(f"  {key}: {value}")
            return 0
    except (ScoreResolutionError, NotImplementedError) as exc:
        print(f"Error: {exc}")
        return 1
    return 2


def _config_path(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "file", None)
    return Path(explicit or os.environ.get("OSAP_CONFIG", "osap.toml"))


def _run_search(args: argparse.Namespace, container: Container) -> int:
    query = args.query
    composer = args.composer
    if args.composer == "__QUERY__" or args.works:
        composer = query
        query = None
    if not query and not composer:
        print("Indica un título o un compositor.")
        return 2
    builder = ResolveRequestBuilder()
    if query:
        builder = builder.text(query)
    if composer:
        builder = builder.composer(composer)
    if getattr(args, "output_format", None):
        builder = builder.format(args.output_format)
    request = builder.build()
    engine = container.work_resolution_engine()
    try:
        ranked = engine.rank(request)
    except ScoreResolutionError as exc:
        print(f"Error: {exc}")
        return 1
    if not ranked:
        print(f"No se encontraron obras para '{query or composer}'.")
        return 1
    seen: dict[tuple[str, str | None], CandidateRepresentation] = {}
    for candidate in ranked:
        key = (candidate.work_descriptor.title, candidate.work_descriptor.composer)
        seen.setdefault(key, candidate)
    print(f"{len(seen)} obra(s) encontrada(s):")
    for (title, comp), candidate in seen.items():
        print(f"  - {title} ({comp or '?'}) [{candidate.provider_id.value}]")
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    """Valida un MusicXML/.mxl y muestra calidad + errores + warnings."""
    from src.osap.domain.acquisition_result import AcquisitionResult
    from src.osap.domain.musical_source import MusicalSource
    from src.osap.domain.output_format import OutputFormat
    from src.osap.domain.quality_report import QualityReport
    from src.osap.domain.value_objects import Confidence, Duration, ProviderId, SourceId
    from src.osap.infrastructure.adapters.validation import BasicValidator

    path = Path(args.path)
    if not path.exists():
        print(f"Error: no existe {path}")
        return 1

    content = path.read_bytes()
    source = MusicalSource(
        source_id=SourceId(f"file-{path.name}"),
        content=content,
        format=OutputFormat.MUSICXML,
        metadata={"title": args.title, "composer": args.composer},
    )
    result = AcquisitionResult(
        provider_id=ProviderId("file"),
        source=source,
        confidence=Confidence(1.0),
        processing_time=Duration(0.0),
        format=OutputFormat.MUSICXML,
    )
    score = BasicValidator().validate(result)
    md = score.metadata
    report_raw = md.get("quality_report")
    report = report_raw if isinstance(report_raw, QualityReport) else None
    dims = report.dimensions if report is not None else {}

    print(f"valid: {md.get('valid', False)}")
    print(f"quality_level: {score.quality_level.value}")
    print("report:")
    for dim, value in dims.items():
        print(f"  {dim.value}: {value:.2f}")
    print(f"errors: {md.get('errors', [])}")
    print(f"warnings: {md.get('warnings', [])}")
    print(f"parts: {md.get('parts', 0)} | measures: {md.get('measures', 0)} | "
          f"notes: {md.get('notes', 0)} | voices: {md.get('voices', 0)} | "
          f"lyrics: {md.get('has_lyrics', False)}")
    return 0 if md.get("valid", False) else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return _run_validate(args)

    config = load_configuration()
    if getattr(args, "library", None):
        config = replace(config, library_root=args.library)
    container = wire(Container(), config)

    if args.command == "resolve":
        return _run_resolve(args, container)
    if args.command == "download":
        return _run_download(args, container)
    if args.command == "catalog":
        return _run_catalog(args, container)
    if args.command == "search":
        return _run_search(args, container)
    raise SystemExit(f"comando desconocido: {args.command}")


def entrypoint() -> None:
    sys.exit(main())


if __name__ == "__main__":
    entrypoint()
