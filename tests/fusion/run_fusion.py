#!/usr/bin/env python3
"""Herramienta de desarrollo para iterar sobre el motor de fusión de OSAP.

El golden dataset guarda UNA SOLA VEZ los datos crudos recibidos de una
consulta (p. ej. ``osap resolve --composer "Mozart"``). Esta herramienta pasa
esos datos por cada fase del tratamiento de nombres y muestra el resultado, de
modo que puedas modificar los módulos y ver al instante dónde falla la fusión.

Fases mostradas por representación:
    RAW → EXTRACTOR → NORMALIZED → WORK KEY
Luego la agrupación (GROUP 1..N) y, en ``--trace``, el desglose por campo de
por qué dos registros se fusionan o no.

Uso
---
    python tests/fusion/run_fusion.py                     # todos los YAML del golden dataset
    python tests/fusion/run_fusion.py --yaml ruta.yaml    # un fichero concreto
    python tests/fusion/run_fusion.py --phases            # imprime las fases de TODOS los casos
    python tests/fusion/run_fusion.py --trace             # además, desglose por pareja (por qué se fusionan)
    python tests/fusion/run_fusion.py --repr 'Symphony No.40,Mozart | Symphony No.40,Gounod'
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.metadata_parser import extract_metadata
from src.osap.application.work_grouper import WorkGrouper
from src.osap.application.work_matcher import WorkMatcher, MergeDecision
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

try:  # Windows consoles default to cp1252; force UTF-8 for musical/accents.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

DEFAULT_DIR = Path(__file__).resolve().parent / "golden dataset"

_KNOWN_COMPOSERS = [
    "giovanni pierluigi da palestrina",
    "tomas luis de victoria",
    "tomás luis de victoria",
    "wolfgang amadeus mozart",
    "w a mozart",
    "wa mozart",
    "johann sebastian bach",
    "js bach",
    "j s bach",
    "ludwig van beethoven",
    "franz schubert",
    "charles gounod",
    "palestrina",
    "victoria",
    "beethoven",
    "schubert",
    "gounod",
    "mozart",
    "bach",
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace(".", " ").replace(",", " ")).strip()


def _infer_composer(title: str) -> tuple[str | None, str]:
    t = _norm(title)
    for composer in _KNOWN_COMPOSERS:
        if t.endswith(f"({composer})"):
            return composer.title(), title[: -(len(composer) + 2)].strip(" ,;:-")
        prefix = composer + " - "
        if t.startswith(prefix):
            return composer.title(), title[len(composer) + 3:].strip(" ,;:-")
        if t.startswith(composer + " ") and len(t) > len(composer) + 1:
            return composer.title(), title[len(composer):].strip(" ,;:-")
        if t.endswith(" " + composer):
            return composer.title(), title[: -(len(composer) + 1)].strip(" ,;:-")
    return None, title.strip()


def _parse_rep(rep: object, index: int) -> CandidateRepresentation:
    if isinstance(rep, str):
        composer, title = _infer_composer(rep)
        provider = "pdmx"
    else:
        assert isinstance(rep, dict)
        title = str(rep.get("title") or "")
        composer = rep.get("composer")
        if composer is None:
            composer, title = _infer_composer(title)
        provider = str(rep.get("provider") or "pdmx")
    return CandidateRepresentation(
        candidate_id=CandidateId(f"r{index}"),
        work_descriptor=WorkDescriptor(
            work_id=WorkId(f"r{index}"),
            title=title,
            composer=str(composer) if composer else None,
        ),
        provider_id=ProviderId(provider),
        format=OutputFormat.MUSICXML,
    )


def _parse_reps(reps: object) -> tuple[CandidateRepresentation, ...]:
    assert isinstance(reps, list) and reps, "sin representaciones"
    return tuple(_parse_rep(r, i) for i, r in enumerate(reps))


def _load_cases(path: Path) -> list[dict[str, object]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if document is None:
        return []
    if isinstance(document, dict):
        cases = document.get("cases", [])
    elif isinstance(document, list):
        cases = document
    else:
        cases = [document]
    return cases if isinstance(cases, list) else []


_BAR = "=" * 75


def _print_phases(candidate: CandidateRepresentation) -> None:
    raw_title = candidate.work_descriptor.title
    raw_composer = candidate.work_descriptor.composer
    meta = extract_metadata(raw_title)
    nm = MetadataNormalizer.normalize(raw_title, raw_composer)

    print(f"\n{_BAR}")
    print("RAW")
    print(f"{_BAR}")
    print(f"{raw_title} - {raw_composer or '(sin compositor)'}  [{candidate.provider_id.value}]")

    print(f"\n{_BAR}")
    print("EXTRACTOR")
    print(f"{_BAR}")
    print(f"title:    {raw_title}")
    print(f"composer: {raw_composer or ''}")
    print(f"catalog:  {meta.catalogue_raw or meta.catalogue or ''}")
    print(f"number:   {meta.work_number or ''}")
    print(f"key:      {meta.key or ''}")

    print(f"\n{_BAR}")
    print("NORMALIZED")
    print(f"{_BAR}")
    print(f"title_key:    {nm.normalized_title}")
    print(f"composer_key: {nm.normalized_composer or ''}")
    print(f"catalog_key:  {nm.normalized_catalog or ''}")
    print(f"number_key:   {nm.normalized_number or ''}")
    print(f"key_key:      {nm.normalized_key or ''}")

    print(f"\n{_BAR}")
    print("WORK KEY")
    print(f"{_BAR}")
    print(nm.signature())


def _fmt_field(label: str, value: float | None) -> str:
    text = "—" if value is None else f"{value:.2f}"
    return f"{label:<10} {text}"


def _print_trace(a: CandidateRepresentation, b: CandidateRepresentation, decision: MergeDecision) -> None:
    print(f"\n{'-' * 75}")
    print("Comparando:")
    print(f"  {a.work_descriptor.title!r}  vs  {b.work_descriptor.title!r}")
    print(f"{'-' * 75}")
    for label, value in decision.breakdown:
        print(f"{_fmt_field(label, value)}")
    print(f"{'FINAL':<10} {decision.score:.2f}")
    print("FUSIONADOS" if decision.merged else "NO FUSIONADOS")
    if decision.evidence:
        print("  evidencia:")
        for e in decision.evidence:
            print(f"    - {e.label}  [weight={e.weight:.2f} conf={e.confidence:.2f}]")
    if decision.work_id:
        print(f"  work_id: {decision.work_id}")


def _format_group(group: object) -> str:
    g = group
    catalog = f"  [cat: {g.work.catalogue_number}]" if g.work.catalogue_number else ""
    lines = [f"    • {g.work.title}  --  {g.work.composer or '?'}{catalog}"]
    for r in g.representations:
        lines.append(f"      {r.provider_id.value.upper():<10} {r.work_descriptor.title}")
    return "\n".join(lines)


def _print_grouping(groups: tuple[object, ...]) -> None:
    for i, group in enumerate(groups, start=1):
        print(f"\n{_BAR}")
        print(f"GROUP {i}")
        print(f"{_BAR}")
        print(_format_group(group))


def _run_case(case: dict[str, object]) -> dict[str, object]:
    candidates = _parse_reps(case.get("representations") or case.get("reps") or [])
    matcher = WorkMatcher()
    grouper = WorkGrouper(matcher)
    groups = grouper.group(candidates)
    pairs = [(a, b, matcher.compare(a, b)) for i, a in enumerate(candidates) for b in candidates[i + 1:]]
    expected = case.get("works_expected", case.get("expected_groups"))
    return {
        "id": case.get("id", "<sin id>"),
        "candidates": candidates,
        "groups": groups,
        "pairs": pairs,
        "expected": int(expected) if expected is not None else None,
    }


def _run_from_string(text: str) -> None:
    reps: list[object] = []
    for token in text.split("|"):
        token = token.strip()
        if not token:
            continue
        if "," in token:
            title, composer = [p.strip() for p in token.split(",", 1)]
            reps.append({"title": title, "composer": composer})
        else:
            reps.append(token)
    case = _run_case({"id": "consulta rápida", "representations": reps})
    for candidate in case["candidates"]:
        _print_phases(candidate)
    for a, b, d in case["pairs"]:
        _print_trace(a, b, d)
    _print_grouping(case["groups"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Itera sobre el motor de fusión de OSAP con el golden dataset.")
    parser.add_argument("--yaml", type=Path, help="Fichero YAML con los casos (por defecto: todo el directorio).")
    parser.add_argument("--phases", action="store_true", help="Imprime las fases (RAW/EXTRACTOR/NORMALIZED/WORK KEY) de todos los casos.")
    parser.add_argument("--trace", action="store_true", help="Imprime el desglose por campo de por qué cada pareja se fusiona o no.")
    parser.add_argument("--repr", help="Caso rápido: 'Title' o 'Title,Composer' separados por '|'.")
    args = parser.parse_args()

    if args.repr:
        _run_from_string(args.repr)
        return 0

    paths: list[Path] = [args.yaml] if args.yaml else sorted(DEFAULT_DIR.glob("*.yaml"))
    total = 0
    failures = 0
    for path in paths:
        if not path.exists():
            print(f"ERROR: no existe {path}")
            return 2
        cases = _load_cases(path)
        if not cases:
            print(f"(sin casos en {path.name})")
            continue
        print(f"\n########## {path.name} ##########")
        for case in cases:
            result = _run_case(case)
            expected = result["expected"]
            groups = result["groups"]
            ok = expected is None or len(groups) == expected
            verdict = (
                "(sin expectativa)" if expected is None
                else f"OK ({len(groups)})" if ok
                else f"FALLO: esperaba {expected}, obtuvo {len(groups)}"
            )
            print(f"\n{'#' * 75}\n# {result['id']}  →  {verdict}\n{'#' * 75}")

            show_phases = args.phases or not ok
            if show_phases:
                for candidate in result["candidates"]:
                    _print_phases(candidate)

            if args.trace:
                for a, b, d in result["pairs"]:
                    _print_trace(a, b, d)

            _print_grouping(groups)
            total += 1
            if not ok:
                failures += 1

    print(f"\n{_BAR}")
    print(f"RESUMEN: {total - failures}/{total} casos correctos")
    if failures:
        print(f"FALLAN {failures} caso(s). El desglose por fases/trace de los casos fallidos ya se imprimió arriba.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
