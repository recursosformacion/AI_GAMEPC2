#!/usr/bin/env python
"""Regresión de resolución sobre `works250.results.json` (baseline del experimento de 250).

FASE 5.1 — medición antes de cambiar reglas. No toca el motor: solo mide el resultado
anterior, genera la **tabla completa de señales** por caso, agrupa los falsos resolved y
provee el scaffolding de evaluación manual (`works250.evaluation.json`).

Señales computables sobre el baseline (el detalle por candidato del motor nuevo, p. ej.
`matching_providers`/`title_score`, requiere ejecutar el matcher sobre un universo
adquirido; aquí se computan las derivables: best/second score, margin, provider count,
candidate count).

Uso:
    python script/resolution_regression.py                       # resumen + flags
    python script/resolution_regression.py --table               # tabla de las 250
    python script/resolution_regression.py --table --tsv out.tsv # tabla a TSV
    python script/resolution_regression.py --emit-evaluation script/works250.evaluation.json
    python script/resolution_regression.py --evaluation script/works250.evaluation.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from src.osap.infrastructure.resolution.work_ranker import decide

_DEFAULT_RESULTS = Path(__file__).resolve().parent / "works250.results.json"
_DEFAULT_EVALUATION = Path(__file__).resolve().parent / "works250.evaluation.json"

# Etiquetas manuales de ground-truth por caso.
_LABELS = ("correct_resolved", "false_resolved", "correct_ambiguous", "false_ambiguous",
           "correct_not_found", "false_not_found", "unknown")


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _evidence_providers(result: dict[str, object]) -> set[str]:
    evidence = result.get("evidence") or []
    return {str(e.get("provider")) for e in evidence if isinstance(e, dict)}


def _composer_null(result: dict[str, object]) -> bool:
    resolved = result.get("resolved") or {}
    composer = resolved.get("composer")
    return not composer or not (composer.get("name") if isinstance(composer, dict) else None)


def analyze(results: list[dict[str, object]]) -> dict[str, object]:
    counts = Counter(str(r.get("status")) for r in results)

    false_resolved: list[tuple[dict[str, object], int]] = []
    composer_null: list[dict[str, object]] = []
    ties: list[dict[str, object]] = []
    should_resolve: list[dict[str, object]] = []

    for r in results:
        status = str(r.get("status"))
        confidence = float(r.get("confidence") or 0)
        providers = _evidence_providers(r)
        candidates = r.get("candidates") or []
        if status == "resolved":
            if _composer_null(r):
                composer_null.append(r)
            # Falso resolved (heurístico): confianza alta pero evidencia débil/un solo provider.
            if confidence >= 0.8 and len(providers) <= 1:
                false_resolved.append((r, len(providers)))
        elif status == "ambiguous":
            confs = [float(c.get("confidence") or 0) for c in candidates if isinstance(c, dict)]
            if len(confs) >= 2 and confs[0] == confs[1]:
                ties.append(r)
        elif status == "not_found" and providers:
            should_resolve.append(r)

    return {
        "counts": dict(counts),
        "total": len(results),
        "false_resolved": false_resolved,
        "composer_null_on_resolved": composer_null,
        "ties_ambiguous": ties,
        "not_found_with_evidence": should_resolve,
    }


def _candidate_summary(result: dict[str, object]) -> str:
    lines: list[str] = []
    candidates = result.get("candidates") or []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        lines.append(
            f"    candidato: name={c.get('name')!r} confidence={c.get('confidence')} "
            f"aliases={c.get('aliases')} ids={c.get('external_ids')}"
        )
    for e in result.get("evidence") or []:
        if isinstance(e, dict):
            lines.append(f"    evidencia: provider={e.get('provider')} kind={e.get('kind')} conf={e.get('confidence')}")
    return "\n".join(lines)


def render(report: dict[str, object]) -> str:
    counts: dict[str, int] = report["counts"]
    total: int = report["total"]
    lines = [
        f"total      : {total}",
        f"resolved   : {counts.get('resolved', 0)}",
        f"ambiguous  : {counts.get('ambiguous', 0)}",
        f"not_found  : {counts.get('not_found', 0)}",
        "",
        f"resolved con composer null          : {len(report['composer_null_on_resolved'])}",
        f"falsos resolved (conf>=0.8, 1 prov) : {len(report['false_resolved'])}",
        f"ambiguous con empate                : {len(report['ties_ambiguous'])}",
        f"not_found con evidencia             : {len(report['not_found_with_evidence'])}",
    ]
    for label, key in (
        ("FALSOS RESOLVED", "false_resolved"),
        ("RESOLVED CON COMPOSER NULL", "composer_null_on_resolved"),
        ("AMBIGUOUS CON EMPATE", "ties_ambiguous"),
        ("NOT_FOUND CON EVIDENCIA (deberían resolverse)", "not_found_with_evidence"),
    ):
        items = report[key]
        if not items:
            continue
        lines.append(f"\n--- {label} ({len(items)}) ---")
        for item in items:
            result = item[0] if isinstance(item, tuple) else item
            lines.append(f"  [{result.get('id')}] status={result.get('status')} conf={result.get('confidence')}")
            lines.append(_candidate_summary(result))
    return "\n".join(lines)


def emit_sample_evaluation(results: list[dict[str, object]], path: Path, n: int = 30, seed: int = 7) -> None:
    """Escribe un muestreo determinista del ground-truth para marcar solo sí/no.

    Cada caso viene precargado con el título y los candidatos disponibles; solo hay que
    rellenar `label` y `correct_candidate` (nombre exacto del candidato correcto, o vacío).
    """
    rng = random.Random(seed)
    sample = rng.sample(results, min(n, len(results)))
    items: dict[str, dict[str, object]] = {}
    for r in sample:
        candidates = [
            {"name": c.get("name"), "confidence": c.get("confidence")}
            for c in (r.get("candidates") or [])
            if isinstance(c, dict)
        ]
        items[str(r.get("id"))] = {
            "label": "unknown",
            "reason": "",
            "note": str(r.get("normalized", {}).get("title_raw") or ""),
            "correct_candidate": "",
            "error_class": "",
            "candidates": candidates,
        }
    doc = {
        "schema": "FASE 5.6 — muestreo de ground-truth. label: correct_resolved|false_resolved|"
        "correct_ambiguous|false_ambiguous|correct_not_found|false_not_found. "
        "correct_candidate: nombre exacto del candidato correcto (o '' si ninguno). "
        "error_class: candidate_missing|candidate_wrong_rank|"
        "candidate_correct_but_insufficient_evidence|provider_metadata_bad|"
        "genuine_ambiguity|genuine_not_found.",
        "n": len(sample),
        "seed": seed,
        "items": items,
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def emit_labeling_sheet(results: list[dict[str, object]], ids: set[str], path: Path) -> None:
    """Hoja de etiquetado legible: para cada caso, input, decisión del sistema, candidatos
    con detalle y evidencia por proveedor. Da el contexto necesario para clasificar."""
    blocks: list[str] = []
    for r in results:
        if str(r.get("id")) not in ids:
            continue
        normalized = r.get("normalized") or {}
        resolved = r.get("resolved") or {}
        work = resolved.get("work") if isinstance(resolved.get("work"), dict) else None
        composer = resolved.get("composer") if isinstance(resolved.get("composer"), dict) else None
        lines = [
            f"=== [{r.get('id')}] status={r.get('status')} conf={r.get('confidence')} ===",
            f"  input title_raw   : {normalized.get('title_raw')}",
            f"  input title (norm): {normalized.get('title')}",
            f"  input composer    : {normalized.get('composer_raw')!r}",
            f"  input catalog     : {normalized.get('catalog')!r}",
            f"  -> elegido work   : {work.get('title') if work else None!r}",
            f"  -> elegido comp   : {composer.get('name') if composer else None!r}",
            "  candidatos:",
        ]
        candidates = r.get("candidates") or []
        for idx, c in enumerate(candidates):
            if not isinstance(c, dict):
                continue
            lines.append(
                f"    {idx}. name={c.get('name')!r} conf={c.get('confidence')} "
                f"aliases={c.get('aliases')} ids={c.get('external_ids')}"
            )
        if not candidates:
            lines.append("    (sin candidatos)")
        lines.append("  evidencia:")
        evidence = r.get("evidence") or []
        for e in evidence:
            if not isinstance(e, dict):
                continue
            lines.append(
                f"    provider={e.get('provider')} kind={e.get('kind')} conf={e.get('confidence')} "
                f"work_title={e.get('work_title')!r} work_catalog={e.get('work_catalog')!r}"
            )
        if not evidence:
            lines.append("    (sin evidencia)")
        blocks.append("\n".join(lines))
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _candidate_scores(result: dict[str, object]) -> list[float]:
    candidates = result.get("candidates") or []
    return sorted((float(c.get("confidence") or 0) for c in candidates if isinstance(c, dict)), reverse=True)


def build_table(results: list[dict[str, object]]) -> list[dict[str, object]]:
    """Tabla de señales por caso, computadas sobre el baseline."""
    rows: list[dict[str, object]] = []
    for r in results:
        normalized = r.get("normalized") or {}
        scores = _candidate_scores(r)
        best = scores[0] if scores else None
        second = scores[1] if len(scores) > 1 else None
        margin = (best - second) if best is not None and second is not None else None
        providers = sorted(_evidence_providers(r))
        rows.append(
            {
                "id": r.get("id"),
                "status": r.get("status"),
                "input_title": normalized.get("title_raw"),
                "input_composer": normalized.get("composer_raw"),
                "best_score": best,
                "second_score": second,
                "margin": round(margin, 4) if margin is not None else None,
                "provider_count": len(providers),
                "matching_providers": ",".join(providers),
                "candidate_count": len(scores),
            }
        )
    return rows


def group_false_resolved(results: list[dict[str, object]]) -> dict[str, object]:
    """Agrupa los falsos resolved (heurístico) por proveedor, nº candidatos y margen."""
    by_provider: Counter[str] = Counter()
    by_candidates: Counter[str] = Counter()
    by_margin: Counter[str] = Counter()
    for r in results:
        if str(r.get("status")) != "resolved":
            continue
        confidence = float(r.get("confidence") or 0)
        if not (confidence >= 0.8 and len(_evidence_providers(r)) <= 1):
            continue
        by_provider[f"{len(_evidence_providers(r))} prov"] += 1
        by_candidates[f"{len(_candidate_scores(r))} cand"] += 1
        scores = _candidate_scores(r)
        margin = None
        if len(scores) >= 2:
            margin = scores[0] - scores[1]
        by_margin[_margin_bin(margin)] += 1
    return {
        "by_provider": dict(sorted(by_provider.items())),
        "by_candidates": dict(sorted(by_candidates.items())),
        "by_margin": dict(sorted(by_margin.items())),
    }


def _margin_bin(margin: float | None) -> str:
    if margin is None:
        return "sin 2º (1 candidato)"
    if margin == 0:
        return "0 (empate)"
    if margin < 0.1:
        return "<0.1"
    return f">=0.1 ({margin:.2f})"


def _table_header() -> list[str]:
    return [
        "id", "status", "input_title", "input_composer",
        "best_score", "second_score", "margin",
        "provider_count", "matching_providers", "candidate_count",
    ]


def table_to_tsv(rows: list[dict[str, object]]) -> str:
    header = _table_header()
    lines = ["\t".join(header)]
    for row in rows:
        lines.append("\t".join("" if row.get(h) is None else str(row.get(h)) for h in header))
    return "\n".join(lines)


def load_evaluation(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    items = doc.get("items") if isinstance(doc, dict) else None
    if not isinstance(items, dict):
        return {}
    return {str(k): v for k, v in items.items() if isinstance(v, dict)}


def emit_evaluation_scaffold(results: list[dict[str, object]], path: Path) -> None:
    """Escribe el scaffold de ground-truth manual (todos 'unknown') para etiquetar."""
    items: dict[str, dict[str, object]] = {}
    for r in results:
        items[str(r.get("id"))] = {
            "label": "unknown",
            "reason": "",
            "note": str(r.get("normalized", {}).get("title_raw") or ""),
            "correct_candidate": "",
        }
    doc = {
        "schema": "FASE 5.6 — ground-truth manual de works250. "
        "label: correct_resolved|false_resolved|correct_ambiguous|false_ambiguous|"
        "correct_not_found|false_not_found. correct_candidate: nombre del candidato "
        "correcto entre candidates (vacío si ninguno / not_found correcto). "
        "reason: por qué se produjo la decisión.",
        "items": items,
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def new_decision_by_result(results: list[dict[str, object]]) -> list[dict[str, object]]:
    """Aplica la decisión evidencia-based del motor a cada caso del baseline.

    Reconstruye candidatos desde la evidencia del baseline y los pasa por
    `work_ranker.decide` (dentro del motor, sin tocar proveedores ni contratos).
    """
    out: list[dict[str, object]] = []
    for r in results:
        resolved = r.get("resolved") or {}
        composer = resolved.get("composer")
        composer_name = composer.get("name") if isinstance(composer, dict) else None
        candidates: list[dict[str, object]] = []
        for e in r.get("evidence") or []:
            if not isinstance(e, dict):
                continue
            candidates.append(
                {
                    "provider": e.get("provider"),
                    "confidence": float(e.get("confidence") or 0),
                    "identity": {"composer": composer_name},
                }
            )
        decision = decide(candidates)
        out.append(
            {
                "id": r.get("id"),
                "old_status": r.get("status"),
                "new_status": decision.status,
                "reason": decision.reason,
                "best_score": decision.ranking.best_score,
                "second_score": decision.ranking.second_score,
                "margin": decision.ranking.margin,
                "matching_providers": decision.ranking.matching_providers,
            }
        )
    return out


def render_new_ranker(rows: list[dict[str, object]]) -> str:
    new_counts = Counter(str(r["new_status"]) for r in rows)
    transitions: Counter[tuple[str, str]] = Counter((str(r["old_status"]), str(r["new_status"])) for r in rows)
    lines = ["NEW RANKER (decisión evidencia-based)", "-" * 34]
    lines.append(f"resolved   : {new_counts.get('resolved', 0)}")
    lines.append(f"ambiguous  : {new_counts.get('ambiguous', 0)}")
    lines.append(f"not_found  : {new_counts.get('not_found', 0)}")
    lines.append("transición old→new:")
    for (old, new), n in sorted(transitions.items()):
        lines.append(f"  {old:10} → {new:10}: {n}")
    return "\n".join(lines)


def render_evaluation(rows: list[dict[str, object]], labels: dict[str, dict[str, object]]) -> str:
    counts: Counter[str] = Counter()
    for row in rows:
        label = str(labels.get(str(row["id"]), {}).get("label") or "unknown")
        counts[label] += 1
    labeled = sum(n for k, n in counts.items() if k != "unknown")
    lines = ["MANUAL EVALUATION", "-" * 20]
    lines.append(f"etiquetados: {labeled} / {len(rows)}")
    for label in _LABELS:
        lines.append(f"{label:20}: {counts[label]}")
    return "\n".join(lines)


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=_DEFAULT_RESULTS, help="Path a works*.results.json")
    parser.add_argument("--table", action="store_true", help="Imprime la tabla de señales de las 250")
    parser.add_argument("--tsv", type=Path, default=None, help="Escribe la tabla en TSV")
    parser.add_argument("--emit-evaluation", type=Path, default=None, help="Genera el scaffold de evaluación manual")
    parser.add_argument("--emit-sample-evaluation", type=Path, default=None, help="Genera un muestreo etiquetable")
    parser.add_argument(
        "--sample-size", type=int, default=30, help="Tamaño del muestreo (con --emit-sample-evaluation)"
    )
    parser.add_argument("--evaluation", type=Path, default=None, help="Fusiona la evaluación manual y muestra métricas")
    parser.add_argument(
        "--sheet",
        type=Path,
        default=None,
        help="Hoja de etiquetado legible para los ids de --evaluation (o todos si no se indica)",
    )
    args = parser.parse_args()
    if not args.results.exists():
        print(f"No existe el fichero de resultados: {args.results}", file=sys.stderr)
        return 2
    doc = load(args.results)
    results = doc.get("results") if isinstance(doc.get("results"), list) else []

    if args.sheet:
        ids = set(load_evaluation(args.evaluation).keys()) if args.evaluation else {str(r.get("id")) for r in results}
        emit_labeling_sheet(results, ids, args.sheet)
        print(f"Hoja de etiquetado: {args.sheet} ({len(ids)} casos)")
        return 0

    if args.emit_evaluation:
        emit_evaluation_scaffold(results, args.emit_evaluation)
        print(f"Scaffold de evaluación generado: {args.emit_evaluation}")
        return 0

    if args.emit_sample_evaluation:
        emit_sample_evaluation(results, args.emit_sample_evaluation, args.sample_size)
        print(f"Muestreo etiquetable generado: {args.emit_sample_evaluation} "
              f"({args.sample_size} casos, seed=7)")
        return 0

    rows = build_table(results)
    if args.tsv:
        args.tsv.write_text(table_to_tsv(rows), encoding="utf-8")
        print(f"Tabla escrita en: {args.tsv}")
        return 0

    if args.table:
        print(table_to_tsv(rows))
        return 0

    if args.evaluation:
        labels = load_evaluation(args.evaluation)
        print(render_evaluation(rows, labels))
        return 0

    report = analyze(results)
    print("BASELINE")
    print("--------")
    print(render(report))
    print()
    grouped = group_false_resolved(results)
    print("AGRUPACIÓN DE FALSOS RESOLVED")
    print("-----------------------------")
    print(f"por proveedor   : {grouped['by_provider']}")
    print(f"por nº candidato: {grouped['by_candidates']}")
    print(f"por margen      : {grouped['by_margin']}")
    print()
    print(render_new_ranker(new_decision_by_result(results)))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
