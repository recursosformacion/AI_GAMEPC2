#!/usr/bin/env python
"""FASE 5.6 — Evaluación guiada por evidencia (offline, sin tocar reglas).

Para cada obra del dataset separa tres preguntas:
  1. ¿La obra correcta está entre los candidatos?          -> candidate recall
  2. ¿Queda primera?                                        -> top-1 accuracy
  3. ¿Hay evidencia suficiente para declararla resolved?    -> resolved precision/recall

Produce una tabla de decisión por señal (proveedores, margen, nº candidatos, compositor)
para descubrir qué señales separan correct de incorrect. **No cambia** el comportamiento
de producción (ni WorksResolution, ni adquisición, ni OpStore, ni contratos).

El ground-truth manual vive en `works250.evaluation.json` (label + correct_candidate).
Las métricas requieren etiquetas; antes de etiquetar, la salida muestra la estructura y
la tabla de señales por caso.

Uso:
    python script/resolution_eval.py
    python script/resolution_eval.py --results script/works250.results.json \
        --evaluation script/works250.evaluation.json --tsv out.tsv
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_DEFAULT_RESULTS = Path(__file__).resolve().parent / "works250.results.json"
_DEFAULT_EVALUATION = Path(__file__).resolve().parent / "works250.evaluation.json"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_scores(result: dict[str, object]) -> list[float]:
    candidates = result.get("candidates") or []
    return sorted((float(c.get("confidence") or 0) for c in candidates if isinstance(c, dict)), reverse=True)


def _candidate_names(result: dict[str, object]) -> list[str]:
    candidates = result.get("candidates") or []
    return [str(c.get("name") or "") for c in candidates if isinstance(c, dict)]


def _evidence_providers(result: dict[str, object]) -> set[str]:
    evidence = result.get("evidence") or []
    return {str(e.get("provider")) for e in evidence if isinstance(e, dict)}


def features(result: dict[str, object]) -> dict[str, object]:
    """Señales por caso, computadas sobre el baseline (la tabla de decisión)."""
    normalized = result.get("normalized") or {}
    resolved = result.get("resolved") or {}
    composer = resolved.get("composer")
    scores = _candidate_scores(result)
    best = scores[0] if scores else None
    second = scores[1] if len(scores) > 1 else None
    margin = (best - second) if best is not None and second is not None else None
    providers = sorted(_evidence_providers(result))
    return {
        "id": result.get("id"),
        "status": result.get("status"),
        "input_title": normalized.get("title_raw"),
        "input_composer": normalized.get("composer_raw"),
        "best_score": best,
        "second_score": second,
        "margin": round(margin, 4) if margin is not None else None,
        "provider_count": len(providers),
        "providers": ",".join(providers),
        "candidate_count": len(scores),
        "composer_null": not composer or not (composer.get("name") if isinstance(composer, dict) else None),
    }


def load_evaluation(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    items = doc.get("items") if isinstance(doc, dict) else None
    return {str(k): v for k, v in items.items() if isinstance(v, dict)} if isinstance(items, dict) else {}


def _is_correct(label: str) -> bool:
    return label.startswith("correct_")


_ERROR_CLASSES = (
    "candidate_missing",
    "candidate_wrong_rank",
    "candidate_correct_but_insufficient_evidence",
    "provider_metadata_bad",
    "genuine_ambiguity",
    "genuine_not_found",
    "",
)


def auto_error_class(result: dict[str, object], label: str, correct_candidate: str) -> str:
    """Clasificación interna del error derivada de las 3 preguntas + label.

    Sobre-escribible manualmente vía `error_class` en la evaluación. Distingue qué
    solución hace falta (búsqueda, ranking, política de confianza, metadata, o ninguno).
    """
    cc = correct_candidate.strip()
    if not cc:
        if label == "correct_not_found":
            return "genuine_not_found"
        if label == "correct_ambiguous":
            return "genuine_ambiguity"
        return "candidate_missing"  # false_not_found / false_ambiguous / false_resolved
    names = [n.lower().strip() for n in _candidate_names(result)]
    target = cc.lower().strip()
    present = target in names
    if not present:
        return "candidate_missing"
    candidates = result.get("candidates") or []
    best = max((c for c in candidates if isinstance(c, dict)), key=lambda c: float(c.get("confidence") or 0))
    first = str(best.get("name") or "").lower().strip() == target
    if not first:
        return "candidate_wrong_rank"
    if str(result.get("status")) == "resolved":
        return ""  # correcto
    return "candidate_correct_but_insufficient_evidence"


def _questions(row: dict[str, object], label: str, correct_candidate: str) -> dict[str, object]:
    names = [n.lower().strip() for n in _candidate_names(row)]
    target = correct_candidate.strip().lower()
    present = bool(target) and target in names
    # ¿Queda primera? El mejor candidato (mayor confidence) == el correcto.
    best_name = ""
    candidates = row.get("candidates") or []
    if isinstance(candidates, list) and candidates:
        best = max((c for c in candidates if isinstance(c, dict)), key=lambda c: float(c.get("confidence") or 0))
        best_name = str(best.get("name") or "").lower().strip()
    first = present and best_name == target
    return {
        "correct_present": present,
        "correct_first": first,
        "decision_correct": _is_correct(label),
    }


def evaluate(rows: list[dict[str, object]], labels: dict[str, dict[str, object]]) -> dict[str, object]:
    labeled = [r for r in rows if labels.get(str(r["id"]), {}).get("label") not in (None, "", "unknown")]
    with_correct = [
        r for r in labeled if str(labels.get(str(r["id"]), {}).get("correct_candidate") or "").strip()
    ]

    present = sum(1 for r in with_correct if _questions(r, str(labels[str(r["id"])]["label"]),
                                                        str(labels[str(r["id"])]["correct_candidate"]))["correct_present"])
    first = sum(1 for r in with_correct if _questions(r, str(labels[str(r["id"])]["label"]),
                                                       str(labels[str(r["id"])]["correct_candidate"]))["correct_first"])
    resolved = [r for r in labeled if r["status"] == "resolved"]
    correct_resolved = sum(1 for r in resolved if _is_correct(str(labels[str(r["id"])]["label"])))

    # should_be_resolved: casos donde el candidato correcto está presente y queda primero
    # (el motor tiene la respuesta correcta arriba y podría legítimamente resolverla).
    should_be_resolved = []
    for r in with_correct:
        lbl = str(labels[str(r["id"])]["label"])
        cc = str(labels[str(r["id"])]["correct_candidate"])
        if _questions(r, lbl, cc)["correct_first"]:
            should_be_resolved.append(r)
    correctly_resolved = sum(
        1 for r in should_be_resolved if str(labels[str(r["id"])]["label"]) == "correct_resolved"
    )

    error_classes: Counter[str] = Counter()
    for r in labeled:
        entry = labels[str(r["id"])]
        manual = str(entry.get("error_class") or "").strip()
        auto = auto_error_class(r, str(entry.get("label") or ""), str(entry.get("correct_candidate") or ""))
        error_classes[manual or auto] += 1

    return {
        "labeled": len(labeled),
        "with_correct_candidate": len(with_correct),
        "candidate_recall": (present / len(with_correct)) if with_correct else None,
        "top1_accuracy": (first / present) if present else None,
        "resolved_precision": (correct_resolved / len(resolved)) if resolved else None,
        "resolved_recall": (correctly_resolved / len(should_be_resolved)) if should_be_resolved else None,
        "should_be_resolved": len(should_be_resolved),
        "error_classes": dict(error_classes),
    }


def decision_table(rows: list[dict[str, object]], labels: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    """Señal → correct / incorrect sobre decisiones etiquetadas."""
    labeled = [r for r in rows if labels.get(str(r["id"]), {}).get("label") not in (None, "", "unknown")]
    signals = {
        "2+ proveedores": lambda f: int(f["provider_count"]) >= 2,
        "1 solo proveedor": lambda f: int(f["provider_count"]) == 1,
        "único candidato": lambda f: int(f["candidate_count"]) == 1,
        "margen alto (>=0.1)": lambda f: f["margin"] is not None and f["margin"] >= 0.1,
        "empate (margen 0)": lambda f: f["margin"] == 0,
        "compositor presente": lambda f: not f["composer_null"],
    }
    out: list[dict[str, object]] = []
    for name, cond in signals.items():
        hit = [r for r in labeled if cond(features(r))]
        if not hit:
            out.append({"signal": name, "correct": 0, "incorrect": 0, "discriminante": None})
            continue
        correct = sum(1 for r in hit if _is_correct(str(labels[str(r["id"])]["label"])))
        incorrect = len(hit) - correct
        out.append(
            {
                "signal": name,
                "correct": correct,
                "incorrect": incorrect,
                "discriminante": round(correct / len(hit), 3) if len(hit) else None,
            }
        )
    return out


def render(metrics: dict[str, object], table: list[dict[str, object]]) -> str:
    lines = [
        "FASE 5.6 — EVALUACIÓN GUIADA POR EVIDENCIA",
        "-" * 40,
        f"etiquetados              : {metrics['labeled']}",
        f"con candidato correcto   : {metrics['with_correct_candidate']}",
        "",
        f"candidate recall (¿está entre los candidatos?): {_fmt(metrics['candidate_recall'])}",
        f"top-1 accuracy (¿queda primera?):              {_fmt(metrics['top1_accuracy'])}",
        f"resolved precision (¿correcta al decir resolved): {_fmt(metrics['resolved_precision'])}",
        f"resolved recall (¿resolvemos las resolubles?):    {_fmt(metrics['resolved_recall'])}"
        f"   (should_be_resolved={metrics['should_be_resolved']})",
        "",
        "CLASIFICACIÓN INTERNA DEL ERROR (error_class)",
        "-" * 40,
    ]
    for cls in _ERROR_CLASSES:
        label = cls or "(correcto)"
        lines.append(f"{label:44}: {metrics['error_classes'].get(cls, 0)}")
    lines += [
        "",
        "TABLA DE DECISIÓN (señal → correct/incorrect, poder discriminante)",
        "-" * 70,
        f"{'señal':24} {'correct':>8} {'incorrect':>10} {'discriminante':>14}",
    ]
    for t in table:
        lines.append(
            f"{t['signal']:24} {t['correct']:>8} {t['incorrect']:>10} {_fmt(t['discriminante']):>14}"
        )
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def table_to_tsv(rows: list[dict[str, object]], labels: dict[str, dict[str, object]]) -> str:
    header = ["id", "status", "input_title", "input_composer", "best_score", "second_score",
              "margin", "provider_count", "providers", "candidate_count", "composer_null",
              "label", "correct_candidate", "error_class", "correct_present", "correct_first"]
    lines = ["\t".join(header)]
    for r in rows:
        label = labels.get(str(r["id"]), {})
        lbl = str(label.get("label") or "")
        cc = str(label.get("correct_candidate") or "")
        ec = str(label.get("error_class") or "").strip() or auto_error_class(r, lbl, cc)
        q = _questions(r, lbl, cc)
        f = features(r)
        values = [f["id"], f["status"], f["input_title"], f["input_composer"], f["best_score"],
                  f["second_score"], f["margin"], f["provider_count"], f["providers"],
                  f["candidate_count"], f["composer_null"], lbl, cc, ec,
                  q["correct_present"], q["correct_first"]]
        lines.append("\t".join("" if v is None else str(v) for v in values))
    return "\n".join(lines)


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=_DEFAULT_RESULTS)
    parser.add_argument("--evaluation", type=Path, default=_DEFAULT_EVALUATION)
    parser.add_argument("--tsv", type=Path, default=None, help="Escribe la tabla por caso")
    args = parser.parse_args()
    if not args.results.exists():
        print(f"No existe: {args.results}", file=sys.stderr)
        return 2
    doc = load(args.results)
    results = doc.get("results") if isinstance(doc.get("results"), list) else []
    labels = load_evaluation(args.evaluation)

    if args.tsv:
        args.tsv.write_text(table_to_tsv(results, labels), encoding="utf-8")
        print(f"Tabla por caso: {args.tsv}")
        return 0

    metrics = evaluate(results, labels)
    print(render(metrics, decision_table(results, labels)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
