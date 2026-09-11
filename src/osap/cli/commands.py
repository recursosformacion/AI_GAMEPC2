"""CLI: commands (F5.6)."""

import argparse
import os
from pathlib import Path
from typing import TYPE_CHECKING

from src.osap.bootstrap.container import Container
from src.osap.cli.requests import _build_request, _choose_candidate, _ordered_candidates, _representations_for
from src.osap.cli.resolve import _progress
from src.osap.domain.errors import ScoreResolutionError

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequestBuilder
from src.osap.domain.value_objects import CatalogId


def _run_download(args: argparse.Namespace, container: Container) -> int:
    if not args.query and not args.composer:
        print("Indica un título o un --composer.")
        return 2
    request = _build_request(args, args.query)
    engine = container.work_resolution_engine()
    print("Searching providers...")
    try:
        ranked = _ordered_candidates(engine, request, on_progress=_progress)
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
    value = explicit or os.environ.get("OSAP_CONFIG") or "osap.toml"
    return Path(value)


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
        ranked = _ordered_candidates(engine, request)
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


def _run_chorus_generate(args: argparse.Namespace) -> int:
    """Chorus (demo): valida el MusicXML → Score real → GenerateMaterialsUseCase → StudyMaterial.

    Chorus es una aplicación independiente de OSAP: este subcomando es un harness de
    demostración del contrato `Score` (OSAP produce el Score con su validador y lo entrega
    en-proceso a Chorus). NO es el entry del producto Chorus (futuro CLI/web propio) y no
    convierte a Chorus en una funcionalidad conceptual de OSAP. No invoca `/works/resolve`
    ni ningún servicio externo.
    """
    from src.chorus.bootstrap.container import Container as ChorusContainer
    from src.chorus.bootstrap.wiring import wire as chorus_wire
    from src.chorus.domain.material_type import MaterialType
    from src.osap.domain.acquisition_result import AcquisitionResult
    from src.osap.domain.musical_source import MusicalSource
    from src.osap.domain.value_objects import Confidence, Duration, ProviderId, SourceId
    from src.osap.infrastructure.adapters.validation import BasicValidator

    path = Path(args.path)
    if not path.exists():
        print(f"Error: no existe {path}")
        return 1
    content = path.read_bytes()
    acquisition = AcquisitionResult(
        provider_id=ProviderId("file"),
        source=MusicalSource(
            source_id=SourceId(f"file-{path.name}"),
            content=content,
            format=OutputFormat.MUSICXML,
            metadata={"title": args.title, "composer": args.composer},
        ),
        confidence=Confidence(1.0),
        processing_time=Duration(0.0),
        format=OutputFormat.MUSICXML,
    )
    score = BasicValidator().validate(acquisition)

    chorus_container = chorus_wire(ChorusContainer())
    use_case = chorus_container.generate_materials_use_case()
    material_type = MaterialType(args.material)
    material = use_case.generate(score, material_type, voice=args.voice)

    print(f"Material generado: {material.material_type.value}")
    print(f"  título: {material.metadata.get('title') or '—'}")
    print(f"  calidad (QualityLevel): {material.metadata.get('quality_level')}")
    content_text = material.content.get("text") if isinstance(material.content, dict) else str(material.content)
    print(content_text or "—")
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    """Valida un MusicXML/.mxl y muestra calidad + errores + warnings."""
    from src.osap.domain.acquisition_result import AcquisitionResult
    from src.osap.domain.musical_source import MusicalSource
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

