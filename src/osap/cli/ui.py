"""CLI: ui (F5.6)."""


from src.osap.application.work_resolution_engine import ProviderReport
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.resolve_result import ResolveResult


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

