"""Golden dataset harness for the work matcher/grouper.

Loads every ``*.yaml`` case under ``docs/pruebasIA/`` and asserts that grouping
the given representations yields the expected number of works. This is the
permanent regression set: add a failing real case here BEFORE fixing the
matching algorithm.

Accepted schema (either):
  - a YAML list of cases, or
  - a mapping ``{cases: [ ... ]}``.
Each case has ``id``, ``expected_groups`` (or ``works_expected``), and
``representations`` (a list of mappings ``{title, composer?, provider?}`` or of
plain title strings). When composer is absent it is inferred from common title
patterns ("Composer - Title", "Title (Composer)", leading composer name).
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml  # type: ignore[import-untyped]

from src.osap.application.work_grouper import WorkGrouper
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

_CASES_DIR = Path(__file__).resolve().parents[1] / "fusion" / "golden dataset"

# Longest-first so "Wolfgang Amadeus Mozart" is matched before "Mozart".
_KNOWN_COMPOSERS = [
    "giovanni pierluigi da palestrina",
    "tomas luis de victoria",
    "tomás luis de victoria",
    "wolfgang amadeus mozart",
    "johann sebastian bach",
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


def _infer_composer(title: str) -> tuple[str | None, str]:
    """Return (composer, clean_title) inferred from common title patterns."""
    stripped = title.strip()
    for composer in _KNOWN_COMPOSERS:
        # "Title (Composer)"
        if stripped.lower().endswith(f"({composer})"):
            base = stripped[: -len(f"({composer})")].strip(" ,;:-")
            return composer.title(), base
        # "Composer - Title"
        prefix = f"{composer} - "
        if stripped.lower().startswith(prefix):
            return composer.title(), stripped[len(prefix) :].strip()
        # Leading composer: "Mozart Requiem KV626"
        if stripped.lower().startswith(composer + " ") and len(stripped) > len(composer) + 1:
            return composer.title(), stripped[len(composer) :].strip()
    return None, stripped


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
        candidate_id=CandidateId(f"g{index}"),
        work_descriptor=WorkDescriptor(
            work_id=WorkId(f"g{index}"),
            title=title,
            composer=str(composer) if composer else None,
        ),
        provider_id=ProviderId(provider),
        format=OutputFormat.MUSICXML,
    )


def _load_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for path in sorted(_CASES_DIR.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if document is None:
            continue
        if isinstance(document, dict):
            document = document.get("cases", [])
        if isinstance(document, list):
            cases.extend(document)
    return cases


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: str(c.get("id", "?")))
def test_golden_merge_case(case: dict[str, object]) -> None:
    reps = case["representations"]
    assert isinstance(reps, list) and reps, f"case {case.get('id')} has no representations"
    candidates = tuple(_parse_rep(r, i) for i, r in enumerate(reps))
    groups = WorkGrouper().group(candidates)
    expected = int(cast("int", case.get("works_expected") or case.get("expected_groups") or 0))
    actual = [g.work.title for g in groups]
    assert len(groups) == expected, f"case {case.get('id')}: expected {expected} work(s), got {len(groups)}: {actual}"
