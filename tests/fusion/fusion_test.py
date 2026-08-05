#!/usr/bin/env python3
"""fusion_test.py — Laboratorio de fusión de obras de OSAP.

Pasa las representaciones crudas de un fichero YAML por las fases del
tratamiento de nombres y ofrece varias vistas:

    python fusion_test.py mozart.yaml            # trace del flujo por representación
    python fusion_test.py mozart.yaml --group    # agrupación final (WORK 1..N)
    python fusion_test.py mozart.yaml --diff     # solo las diferencias entre campos
    python fusion_test.py mozart.yaml --trace    # DECISION (por qué se fusiona) por pareja

El fichero YAML puede ser:
  - una lista de representaciones ({title, composer?, provider?} o strings), o
  - un mapeo {cases: [ {representations: [...]}, ... ]} (se combinan todas).

Solo usa los módulos reales del pipeline. Prototipo: no toca nada fuera de
tests/fusion.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import fields
from pathlib import Path

import yaml

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.metadata_parser import extract_metadata
from src.osap.application.work_grouper import WorkGrouper
from src.osap.application.work_grouping_matcher import WorkGroupingMatcher, MergeDecision
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

_BAR = "-" * 55
_DOWN = "\u2193"

_FORMATS = {
    "musicxml": OutputFormat.MUSICXML,
    "mei": OutputFormat.MEI,
    "pdf": OutputFormat.PDF,
    "midi": OutputFormat.MIDI,
    "score": OutputFormat.SCORE,
    "audio": OutputFormat.SCORE,
}

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
        fmt = OutputFormat.MUSICXML
        downloadable = True
        manual_download = False
        download_url = None
        license = None
    else:
        assert isinstance(rep, dict)
        title = str(rep.get("title") or "")
        composer = rep.get("composer")
        if composer is None:
            composer, title = _infer_composer(title)
        provider = str(rep.get("provider") or "pdmx")
        fmt = _FORMATS.get(str(rep.get("format") or "").lower(), OutputFormat.SCORE)
        downloadable = bool(rep.get("downloadable", True))
        manual_download = bool(rep.get("manual_download", False))
        download_url = rep.get("download_url")
        license = rep.get("license")
    return CandidateRepresentation(
        candidate_id=CandidateId(f"r{index}"),
        work_descriptor=WorkDescriptor(
            work_id=WorkId(f"r{index}"),
            title=title,
            composer=str(composer) if composer else None,
        ),
        provider_id=ProviderId(provider),
        format=fmt,
        downloadable=downloadable,
        manual_download=manual_download,
        download_url=str(download_url) if download_url else None,
        license=str(license) if license else None,
    )


def _parse_reps(reps: object) -> tuple[CandidateRepresentation, ...]:
    assert isinstance(reps, list), "representaciones inválidas"
    return tuple(_parse_rep(r, i) for i, r in enumerate(reps))


def load_reps(path: Path) -> list[CandidateRepresentation]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(document, dict):
        cases = document.get("cases", [])
        reps_raw: list[object] = []
        for case in cases:
            reps_raw.extend(case.get("representations") or [])
    elif isinstance(document, list):
        reps_raw = list(document)
    else:
        reps_raw = []
    return [_parse_rep(r, i) for i, r in enumerate(reps_raw)]


def load_cases(path: Path) -> list[dict[str, object]]:
    """Carga casos con expectativa: cada uno con `works_expected` (o `expected_groups`)."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(document, dict):
        cases = document.get("cases", [])
    elif isinstance(document, list):
        cases = document
    else:
        cases = [document]
    return cases if isinstance(cases, list) else []


def _build(reps: list[CandidateRepresentation]) -> tuple[WorkGroupingMatcher, list[object], dict[CandidateId, tuple[int, str]]]:
    matcher = WorkGroupingMatcher()
    groups = WorkGrouper(matcher).group(tuple(reps))
    rep_to_group = {
        rep.candidate_id: (i, group.work.title)
        for i, group in enumerate(groups)
        for rep in group.representations
    }
    return matcher, groups, rep_to_group


# --------------------------------------------------------------------------- #
# VISTA 1 · trace del flujo por representación
# --------------------------------------------------------------------------- #
def cmd_phases(reps: list[CandidateRepresentation]) -> None:
    matcher, groups, rep_to_group = _build(reps)
    print(f"{len(reps)} representaciones")
    by_provider: dict[str, list[CandidateRepresentation]] = {}
    for rep in reps:
        by_provider.setdefault(rep.provider_id.value, []).append(rep)
    for provider in sorted(by_provider):
        print(f"\n{_BAR}\n{provider.upper()}\n{_BAR}")
        for rep in by_provider[provider]:
            meta = extract_metadata(rep.work_descriptor.title)
            nm = MetadataNormalizer.normalize(rep.work_descriptor.title, rep.work_descriptor.composer)
            group_index, cli_title = rep_to_group.get(rep.candidate_id, (0, rep.work_descriptor.title))
            print("\nINPUT")
            print(rep.work_descriptor.title)
            print(f"\n{_DOWN} PARSER")
            print(f"  title    {rep.work_descriptor.title!r}")
            print(f"  composer {rep.work_descriptor.composer!r}")
            print(f"  catalog  {meta.catalogue_raw or meta.catalogue or ''!r}")
            print(f"  number   {meta.work_number or ''!r}")
            print(f"  key      {meta.key or ''!r}")
            print(f"\n{_DOWN} NORMALIZER")
            print(f"  title_key    {nm.normalized_title!r}")
            print(f"  composer_key {nm.normalized_composer or ''!r}")
            print(f"  catalog_key  {nm.normalized_catalog or ''!r}")
            print(f"  number_key   {nm.normalized_number or ''!r}")
            print(f"  key_key      {nm.normalized_key or ''!r}")
            print(f"\n{_DOWN} MATCHER")
            print(f"  merge_key  {nm.signature()}")
            print(f"\n{_DOWN} GROUP")
            print(f"  work={group_index + 1}")
            print(f"\n{_DOWN} CLI")
            print(cli_title)
            print(_BAR)


# --------------------------------------------------------------------------- #
# VISTA 2 · agrupación final
# --------------------------------------------------------------------------- #
def cmd_group(reps: list[CandidateRepresentation]) -> None:
    matcher, groups, _ = _build(reps)
    for i, group in enumerate(groups, start=1):
        print(f"\n{_BAR}\nWORK {i}\n{_BAR}")
        print(group.work.title)
        if group.work.catalogue_number:
            print(f"Catálogo: {group.work.catalogue_number}")
        if group.work.composer:
            print(f"Compositor: {group.work.composer}")
        print("\nRepresentaciones")
        for rep in group.representations:
            print(f"\n{rep.provider_id.value.upper()}")
            print(rep.work_descriptor.title)


# --------------------------------------------------------------------------- #
# VISTA 3 · diferencias entre campos
# --------------------------------------------------------------------------- #
def _raw_field(name: str, rep: CandidateRepresentation) -> str:
    meta = extract_metadata(rep.work_descriptor.title)
    mapping = {
        "catalog": meta.catalogue_raw or meta.catalogue or "",
        "title": rep.work_descriptor.title,
        "composer": rep.work_descriptor.composer or "",
        "number": meta.work_number or "",
        "key": meta.key or "",
    }
    return mapping[name]


def _norm_field(name: str, rep: CandidateRepresentation) -> str | None:
    nm = MetadataNormalizer.normalize(rep.work_descriptor.title, rep.work_descriptor.composer)
    mapping = {
        "catalog": nm.normalized_catalog,
        "title": nm.normalized_title,
        "composer": nm.normalized_composer,
        "number": nm.normalized_number,
        "key": nm.normalized_key,
    }
    return mapping[name]


def cmd_diff(reps: list[CandidateRepresentation]) -> None:
    matcher, groups, _ = _build(reps)
    for group in groups:
        primary = group.primary
        if primary is None:
            continue
        print(f"\n{_BAR}\nWORK: {group.work.title}\n{_BAR}")
        for member in group.representations:
            if member.candidate_id == primary.candidate_id:
                continue
            idx = int(member.candidate_id.value[1:]) + 1
            for name in ("catalog", "title", "composer", "number", "key"):
                raw_a = _raw_field(name, member)
                raw_b = _raw_field(name, primary)
                if raw_a != raw_b:
                    norm_a = _norm_field(name, member)
                    norm_b = _norm_field(name, primary)
                    ok = norm_a is not None and norm_a == norm_b
                    print(f"\nRepresentación {idx}")
                    print(name.upper())
                    print(f"  {member.provider_id.value.upper():<10} {raw_a}")
                    print(f"  {primary.provider_id.value.upper():<10} {raw_b}")
                    print("NORMALIZADO")
                    print(f"  {norm_a or ''}")
                    print(f"  {norm_b or ''}")
                    print("OK" if ok else "NO MATCH")


# --------------------------------------------------------------------------- #
# VISTA 4 · DECISION (por qué se fusiona cada pareja)
# --------------------------------------------------------------------------- #
def _print_decision(a: CandidateRepresentation, b: CandidateRepresentation, d: MergeDecision) -> None:
    nm = MetadataNormalizer.normalize(a.work_descriptor.title, a.work_descriptor.composer)
    print(f"\nDECISION  {a.work_descriptor.title!r}  vs  {b.work_descriptor.title!r}")
    print(f"  score:    {d.score:.2f}")
    print(f"  decision: {d.decision.value}")
    print("  evidence:")
    for e in d.evidence:
        extra = ", ".join(f"{f.name}={getattr(e, f.name)}" for f in fields(e) if f.name not in ("label", "weight", "confidence"))
        print(f"    - {e.label}  [weight={e.weight:.2f} conf={e.confidence:.2f}] {extra}".rstrip())
    print("  KEY")
    print(f"    title:  {nm.normalized_title or '-'}")
    print(f"    number: {nm.normalized_number or '-'}")
    print(f"    key:    {nm.normalized_key or '-'}")
    print("  WORK_ID")
    print(f"    {d.work_id}")


def cmd_trace(reps: list[CandidateRepresentation]) -> None:
    matcher, groups, _ = _build(reps)
    for group in groups:
        primary = group.primary
        if primary is None:
            continue
        print(f"\n{_BAR}\nWORK: {group.work.title}\n{_BAR}")
        for member in group.representations:
            if member.candidate_id == primary.candidate_id:
                continue
            d = matcher.compare(member, primary)
            _print_decision(member, primary, d)


# --------------------------------------------------------------------------- #
# VISTA · campos de cada obra y su procedencia
# --------------------------------------------------------------------------- #
_GENRE_MAP = {
    "symphony": "Sinfonía", "sinfonie": "Sinfonía",
    "concerto": "Concierto", "sonata": "Sonata", "nocturne": "Nocturno",
    "requiem": "Réquiem", "mass": "Misa", "missa": "Misa", "messe": "Misa",
    "motet": "Motete", "motete": "Motete", "cantata": "Cantata", "opera": "Ópera",
    "lied": "Lied", "hymn": "Himno", "chorale": "Coral", "overture": "Obertura",
    "serenade": "Serenata", "duo": "Dúo", "trio": "Trío", "quartet": "Cuarteto",
    "ave": "Ave", "salve": "Salve", "miserere": "Miserere", "jubilate": "Jubilate",
}


def _genre_from(title: str) -> str | None:
    for token in _norm(title).split():
        if token in _GENRE_MAP:
            return _GENRE_MAP[token]
    return None


def _extract_for(rep: CandidateRepresentation) -> object:
    return extract_metadata(rep.work_descriptor.title)


def _field_provenance(group: object, attr: str) -> CandidateRepresentation | None:
    for rep in group.representations:
        if getattr(rep.work_descriptor, attr, None):
            return rep
    return None


def _field_extracted(group: object, name: str) -> CandidateRepresentation | None:
    for rep in group.representations:
        meta = _extract_for(rep)
        if getattr(meta, name, None):
            return rep
    return None


def _print_work_fields(group: object) -> None:
    work = group.work
    best = group.primary
    rows: list[tuple[str, str, str]] = []

    def src(rep: CandidateRepresentation | None) -> str:
        return rep.provider_id.value.upper() if rep else "—"

    rows.append(
        (
            "título",
            work.title,
            f"display=clean_display_title({best.work_descriptor.title!r})  [{src(best)}]",
        )
    )

    comp_src = _field_provenance(group, "composer")
    rows.append(
        (
            "compositor",
            work.composer or "-",
            f"canonical_composer({comp_src.work_descriptor.composer!r})  [{src(comp_src)}]"
            if comp_src
            else "—",
        )
    )

    cat_src = _field_extracted(group, "catalogue")
    rows.append(
        (
            "catálogo",
            work.catalogue_number or "-",
            f"extract_metadata({cat_src.work_descriptor.title!r}).catalogue  [{src(cat_src)}]"
            if cat_src
            else "—",
        )
    )

    num_src = _field_extracted(group, "work_number")
    rows.append(
        (
            "número",
            _norm_show(_field_extracted_value(group, "work_number")),
            f"extract_metadata(...).work_number  [{src(num_src)}]" if num_src else "—",
        )
    )

    key_src = _field_extracted(group, "key")
    rows.append(
        ("tonalidad", work.key or "-", f"extract_metadata(...).key  [{src(key_src)}]" if key_src else "—")
    )

    opus_src = _field_extracted(group, "opus")
    rows.append(
        (
            "opus",
            _norm_show(_field_extracted_value(group, "opus")),
            f"extract_metadata(...).opus  [{src(opus_src)}]" if opus_src else "—",
        )
    )

    genre = _genre_from(best.work_descriptor.title)
    rows.append(
        (
            "tipo/género",
            genre or "-",
            f"inferido del título {best.work_descriptor.title!r}  [{src(best)}]",
        )
    )

    mov_src = _field_provenance(group, "movement")
    rows.append(("movimiento", work.movement or "-", f"work_descriptor.movement  [{src(mov_src)}]" if mov_src else "—"))

    rows.append(("clave interna", work.canonical_key or "-", "NormalizedMetadata.signature()"))

    w = max(len(r[0]) for r in rows)
    print(f"\n  Campos de la obra — {work.title}")
    for label, value, origin in rows:
        print(f"    {label:<{w}}  {value:<24}  {origin}")


def _field_extracted_value(group: object, name: str) -> str | None:
    for rep in group.representations:
        meta = _extract_for(rep)
        v = getattr(meta, name, None)
        if v:
            return str(v)
    return None


def _norm_show(v: str | None) -> str:
    return v if v else "-"


def cmd_fields(reps: list[CandidateRepresentation]) -> None:
    matcher, groups, _ = _build(reps)
    for i, group in enumerate(groups, start=1):
        print(f"\n{_BAR}\nWORK {i}\n{_BAR}")
        print(group.work.title)
        if group.work.catalogue_number:
            print(f"Catálogo: {group.work.catalogue_number}")
        if group.work.composer:
            print(f"Compositor: {group.work.composer}")
        _print_work_fields(group)


# --------------------------------------------------------------------------- #
# VISTA 5 · medición de precisión sobre casos con expectativa
# --------------------------------------------------------------------------- #
def _case_missing_evidence(case: dict[str, object]) -> str:
    """Qué evidencias faltan en el caso (para diagnosticar un FAIL)."""
    from identity import parse_identity

    reps_raw = case.get("representations") or []
    present: dict[str, bool] = {}
    for raw in reps_raw:
        rep = _parse_rep(raw, 0)
        wid = parse_identity(rep.work_descriptor.title, rep.work_descriptor.composer)
        for name, value in (
            ("catalog", wid.catalog),
            ("number", wid.work_number),
            ("key", wid.key),
            ("movement", wid.movement),
            ("type", wid.work_type),
        ):
            present[name] = present.get(name, False) or bool(value)
    missing = [name for name, ok in present.items() if not ok]
    return ("falta " + ", ".join(missing)) if missing else "evidencia completa"


def cmd_measure(path: Path) -> None:
    cases = load_cases(path)
    grouper = WorkGrouper()
    total = 0
    passed = 0
    under = 0
    over = 0
    tp = fp = fn = 0
    print(f"\nMedición sobre {path.name}\n{_BAR}")
    for case in cases:
        reps = _parse_reps(case.get("representations") or [])
        if not reps:
            continue
        expected = case.get("works_expected") or case.get("expected_groups")
        if expected is None:
            continue
        groups = grouper.group(tuple(reps))
        got = len(groups)
        expected = int(expected)
        total += 1
        ok = got == expected
        if ok:
            passed += 1
        elif got < expected:
            under += 1
        else:
            over += 1
        mark = "PASS" if ok else "FAIL"
        reason = "" if ok else f"  → {_case_missing_evidence(case)}"
        print(f"  [{mark}] {case.get('id', '?')}  (esperaba {expected}, obtuvo {got}){reason}")

        # TP/FP/FN por parejas, si las representaciones llevan etiqueta `work`.
        tags = [raw.get("work") if isinstance(raw, dict) else None for raw in (case.get("representations") or [])]
        if any(t for t in tags):
            group_of = {rep.candidate_id: g for g in groups for rep in g.representations}
            for i in range(len(reps)):
                for j in range(i + 1, len(reps)):
                    should = tags[i] == tags[j]
                    merged = group_of[reps[i].candidate_id] is group_of[reps[j].candidate_id]
                    if should and merged:
                        tp += 1
                    elif not should and merged:
                        fp += 1
                    elif should and not merged:
                        fn += 1

    print(f"\nPrecisión por caso: {passed}/{total} correctos  ({100.0 * passed / total:.1f}%)" if total else "sin casos")
    if under or over:
        print(f"  sobre-fusión (demasiadas obras juntas): {over}")
        print(f"  sub-fusión  (obras separadas de más):    {under}")
    if tp or fp or fn:
        print(f"\nMatcher (por parejas, casos con etiqueta `work`):")
        print(f"  True Positive  {tp}")
        print(f"  False Positive {fp}")
        print(f"  False Negative {fn}")
    return passed == total


def cmd_identity(reps: list[CandidateRepresentation]) -> None:
    from collections import defaultdict

    from identity import parse_identity

    print(f"{len(reps)} representaciones")
    by_sig: dict[str, list[str]] = defaultdict(list)
    for rep in reps:
        wid = parse_identity(rep.work_descriptor.title, rep.work_descriptor.composer)
        by_sig[wid.signature()].append(f"{rep.provider_id.value.upper()} · {rep.work_descriptor.title}")
        print(f"\n{_BAR}\nRAW\n{rep.work_descriptor.title}  ({rep.provider_id.value})")
        print("\nIDENTITY")
        print(f"  composer      {wid.composer_id or '-'}")
        print(f"  catalog       {wid.catalog or '-'}")
        print(f"  type          {wid.work_type or '-'}")
        print(f"  liturgical    {wid.liturgical_form or '-'}")
        print(f"  number        {wid.work_number or '-'}")
        print(f"  key           {wid.key or '-'}")
        print(f"  movement      {wid.movement or '-'}")
        print("\nCONFIDENCE")
        for name, value in wid.confidence.items():
            print(f"  {name:<12} {value:.2f}")
        print("\nSIGNATURE")
        print(wid.signature())

    print(f"\n{_BAR}\nAGRUPACIÓN POR IDENTIDAD (signature)")
    for sig, titles in sorted(by_sig.items()):
        print(f"\n  {sig}  ({len(titles)})")
        for t in titles:
            print(f"      - {t}")


def cmd_statistics(path: Path) -> None:
    from identity import parse_identity

    paths: list[Path] = sorted(path.glob("*.yaml")) if path.is_dir() else [path]
    reps: list[CandidateRepresentation] = []
    for p in paths:
        reps.extend(load_reps(p))
    if not reps:
        print("Sin representaciones.")
        return

    ids = [parse_identity(r.work_descriptor.title, r.work_descriptor.composer) for r in reps]

    def present(identity: object, field: str) -> bool:
        if field == "composer":
            return bool(identity.composer_id)
        if field == "catalog":
            return bool(identity.catalog)
        if field == "number":
            return bool(identity.work_number)
        if field == "key":
            return bool(identity.key)
        if field == "movement":
            return bool(identity.movement)
        if field == "type":
            return bool(identity.work_type)
        if field == "liturgical":
            return bool(identity.liturgical_form)
        return False

    n = len(reps)
    print(f"\nEstadísticas sobre {len(paths)} fichero(s)\n{_BAR}")
    print(f"Representaciones: {n}")
    print()
    print("Presencia de campos:")
    fields = ["composer", "catalog", "number", "movement", "key", "type", "liturgical"]
    for field in fields:
        count = sum(1 for w in ids if present(w, field))
        print(f"  {field:<12} {100.0 * count / n:5.1f} %  ({count})")

    # Agrupar POR FICHERO (rápido); acumular evidencias de obra.
    grouper = WorkGrouper()
    works_cat = works_num = works_key = works_mov = works_both = works_title_only = 0
    works_multi_cat = works_multi_num = 0
    w = 0
    for p in paths:
        file_reps = load_reps(p)
        if not file_reps:
            continue
        groups = grouper.group(tuple(file_reps))
        w += len(groups)
        for group in groups:
            gids = [parse_identity(r.work_descriptor.title, r.work_descriptor.composer) for r in group.representations]
            has_cat = any(g.catalog for g in gids)
            has_num = any(g.work_number for g in gids)
            has_key = any(g.key for g in gids)
            has_mov = any(g.movement for g in gids)
            cats = {g.catalog for g in gids if g.catalog}
            nums = {g.work_number for g in gids if g.work_number}
            works_cat += has_cat
            works_num += has_num
            works_key += has_key
            works_mov += has_mov
            works_both += bool(has_cat and has_num)
            works_title_only += not (has_cat or has_num or has_key or has_mov)
            works_multi_cat += len(cats) > 1
            works_multi_num += len(nums) > 1
    print(f"\nObras (según el matcher, por fichero): {w}")
    print(f"  con catálogo          {works_cat}")
    print(f"  con número            {works_num}")
    print(f"  con tonalidad         {works_key}")
    print(f"  con movimiento        {works_mov}")
    print(f"  catálogo + número     {works_both}   (evidencia complementaria: No40 ≈ K550)")
    print(f"  varios catálogos      {works_multi_cat}   (posible contradicción)")
    print(f"  varios números        {works_multi_num}   (posible contradicción)")
    print(f"  solo título (sin evidencia estructurada) {works_title_only}")

    print(f"\nNota: {works_both} obra(s) dependen de que una KnowledgeBase sepa que No40 ≈ K550; "
          f"{works_title_only} dependen del título.")


def _jaccard(a: str, b: str) -> float:
    if a == b:
        return 1.0
    ta = set(a.split())
    tb = set(b.split())
    if not ta and not tb:
        return 1.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def cmd_explain(reps: list[CandidateRepresentation]) -> None:
    from identity import parse_identity

    matcher = WorkGroupingMatcher()
    grouper = WorkGrouper(matcher)
    groups = grouper.group(tuple(reps))
    rep_to_group = {
        rep.candidate_id: group
        for group in groups
        for rep in group.representations
    }

    # Cadena de evidencias por representación (dentro de su grupo).
    for group in groups:
        primary = group.primary
        if primary is None:
            continue
        print(f"\n{_BAR}\nWORK: {group.work.title}  ({len(group.representations)} reps)\n{_BAR}")
        for member in group.representations:
            wid = parse_identity(member.work_descriptor.title, member.work_descriptor.composer)
            nm_p = MetadataNormalizer.normalize(primary.work_descriptor.title, primary.work_descriptor.composer)
            nm_m = MetadataNormalizer.normalize(member.work_descriptor.title, member.work_descriptor.composer)
            sim = _jaccard(nm_m.normalized_title, nm_p.normalized_title)
            print(f"\n  {member.provider_id.value.upper()} · {member.work_descriptor.title}")
            print(f"    composer  {'exact' if wid.composer_id else 'missing'}")
            print(f"    catalog   {wid.catalog or 'missing'}")
            print(f"    title     {sim * 100:.0f} %")
            print(f"    number    {wid.work_number or 'missing'}")
            print(f"    key       {wid.key or 'missing'}")
            print(f"    movement  {wid.movement or 'missing'}")
            print(f"    RESULT    MERGED")

    # Por qué NO se fusionaron: parejas de grupos distintos con score cercano al umbral.
    print(f"\n{_BAR}\nPOR QUÉ NO SE FUSIONARON (cercanas al umbral {matcher.threshold:.2f})\n{_BAR}")
    shown = 0
    for i, a in enumerate(reps):
        for b in reps[i + 1:]:
            if rep_to_group.get(a.candidate_id) is rep_to_group.get(b.candidate_id):
                continue  # ya fusionadas
            decision = matcher.compare(a, b)
            if decision.score >= matcher.threshold - 0.25 and not decision.merged:
                shown += 1
                print(f"\n  {a.provider_id.value.upper()} · {a.work_descriptor.title}")
                print(f"  {b.provider_id.value.upper()} · {b.work_descriptor.title}")
                for label, value in decision.breakdown:
                    print(f"    {label:<10} {('—' if value is None else f'{value:.2f}')}")
                print(f"    {'matcher score':<10} {decision.score:.2f}   threshold {matcher.threshold:.2f}")
                print("    NO MERGED")
    if shown == 0:
        print("  (sin casos cercanos al umbral)")


def cmd_resources(reps: list[CandidateRepresentation]) -> None:
    from src.osap.application.resource_resolver import ResourceResolver

    matcher, groups, _ = _build(reps)
    resolver = ResourceResolver()
    for i, group in enumerate(groups, start=1):
        rw = resolver.resolve(group)
        print(f"\n{_BAR}\nWORK {i} · {rw.title}  --  {rw.composer or '?'}")
        if rw.catalog:
            print(f"Catálogo: {rw.catalog}")
        print("Recursos:")
        for resource in rw.resources:
            label = f"{resource.format.upper()}" + (f" · {resource.role}" if resource.role else "")
            print(f"  [{label}]")
            for rep in resource.representations:
                acq = rw.acquisition_for(rep)
                prov = rep.provider_id.value.upper()
                if acq is None:
                    print(f"      - {prov:<10} (sin adquisición)")
                    continue
                method = acq.method.value
                extra = ""
                if acq.url:
                    extra = f"  url={acq.url}"
                elif acq.local_path:
                    extra = f"  path={acq.local_path}"
                elif acq.reason:
                    extra = f"  reason={acq.reason}"
                print(f"      - {prov:<10} {method:<12}{extra}")


def cmd_lexicon(reps: list[CandidateRepresentation]) -> None:
    from src.osap.application.lexicon import Lexicon

    lexicon_path = Path(__file__).resolve().parents[2] / "lexicon"
    lexicon = Lexicon(lexicon_path, debug=True)
    print("\n############ DEBUG MODE ACTIVE ############")
    print(f"Léxico: {lexicon_path}")
    for rep in reps:
        result = lexicon.classify(rep.work_descriptor.title)
        ident = ", ".join(result.identity) or "-"
        move = ", ".join(result.movement) or "-"
        desc = ", ".join(result.descriptive) or "-"
        unk = ", ".join(result.unknowns) or "-"
        print(f"\n  {rep.provider_id.value.upper()} · {rep.work_descriptor.title}")
        print(f"    identidad   : {ident}")
        print(f"    movimiento  : {move}")
        print(f"    descriptivo : {desc}")
        print(f"    nº obra     : {result.work_number or '-'}")
        print(f"    desconocidos: {unk}")
    print("\n" + "=" * 55)
    print(f"DEBUG: {len(reps)} títulos clasificados.")
    print(f"DEBUG: términos desconocidos nuevos (música) añadidos a sinAsignar.yaml: {lexicon.new_unknowns}")
    print(f"DEBUG: términos no musicales nuevos añadidos a sinAsignarTexto.yaml: {lexicon.new_text}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Laboratorio de fusión de obras de OSAP.")
    parser.add_argument("yaml", type=Path, help="Fichero YAML o carpeta con las representaciones (p. ej. mozart.yaml).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--group", action="store_true", help="Muestra la agrupación final (WORK 1..N).")
    group.add_argument("--diff", action="store_true", help="Muestra solo las diferencias entre campos.")
    group.add_argument("--trace", action="store_true", help="Muestra DECISION (por qué se fusiona) por pareja.")
    group.add_argument("--measure", action="store_true", help="Mide la precisión sobre casos con expectativa.")
    group.add_argument("--fields", action="store_true", help="Muestra los campos de cada obra y cómo se obtuvieron.")
    group.add_argument("--identity", action="store_true", help="Muestra la IDENTIDAD musical de cada representación.")
    group.add_argument("--statistics", action="store_true", help="Muestra estadísticas de presencia de campos y evidencias.")
    group.add_argument("--explain", action="store_true", help="Explica la cadena de evidencias y por qué no se fusionó.")
    group.add_argument("--resources", action="store_true", help="Muestra la resolución por recursos (Work → Resource → Representation).")
    group.add_argument("--lexicon", action="store_true", help="Clasifica títulos con el léxico musical (modo DEBUG).")
    args = parser.parse_args()

    if not args.yaml.exists():
        print(f"ERROR: no existe {args.yaml}")
        return 2

    if args.statistics:
        return 0 if cmd_statistics(args.yaml) else 1

    reps = load_reps(args.yaml)
    if not reps:
        print(f"Sin representaciones en {args.yaml.name}")
        return 0

    if args.group:
        cmd_group(reps)
    elif args.diff:
        cmd_diff(reps)
    elif args.trace:
        cmd_trace(reps)
    elif args.fields:
        cmd_fields(reps)
    elif args.identity:
        cmd_identity(reps)
    elif args.explain:
        cmd_explain(reps)
    elif args.resources:
        cmd_resources(reps)
    elif args.lexicon:
        cmd_lexicon(reps)
    elif args.measure:
        return 0 if cmd_measure(args.yaml) else 1
    else:
        cmd_phases(reps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
