"""F3.4 — IUniverseResolver (pipeline V2.1) y serialización canónica.

Verifica: agrupación por identidad, ranking, merge por grupo, determinismo ante cambio de
orden de entrada y estabilidad de la serialización (mismo resultado lógico → mismo JSON;
cambio real → JSON distinto).
"""

import json
import random

from src.osap.application.universe_resolution import V21UniverseResolver
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.resolution.resolution_serializer import (
    canonical_json,
    item_id,
    resolved_group_payload,
)


def _descriptor(title: str, composer: str | None = None, catalogue: str | None = None) -> WorkDescriptor:
    return WorkDescriptor(
        work_id=WorkId("work"),
        title=title,
        composer=composer,
        catalogue_number=catalogue,
    )


def _rep(
    pid: str,
    title: str,
    composer: str | None = None,
    catalogue: str | None = None,
    fmt: OutputFormat = OutputFormat.MUSICXML,
    confidence: float = 0.9,
    remote_id: str | None = None,
) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(f"{pid}-{remote_id or '1'}"),
        work_descriptor=_descriptor(title, composer, catalogue),
        provider_id=ProviderId(pid),
        format=fmt,
        confidence=Confidence(confidence),
        remote_id=remote_id,
    )


def _payloads(resolver: V21UniverseResolver, candidates: tuple[CandidateRepresentation, ...]) -> list[str]:
    result = resolver.resolve(candidates)
    payloads = [resolved_group_payload(gr) for gr in result.groups]
    payloads.sort(key=lambda p: item_id(p))
    return [canonical_json(p) for p in payloads]


def _resolver() -> V21UniverseResolver:
    return V21UniverseResolver()


def test_empty_universe_resolves_to_empty() -> None:
    result = _resolver().resolve(())
    assert result.groups == ()


def test_single_candidate_produces_one_group() -> None:
    resolver = _resolver()
    result = resolver.resolve((_rep("omr", "Ave Verum", "Mozart"),))
    assert len(result.groups) == 1
    group = result.groups[0]
    assert len(group.group.representations) == 1
    assert group.merged.merged_descriptor.title == "Ave Verum"
    assert group.score.score >= 0.0


def test_multiple_providers_same_work_group_into_one() -> None:
    candidates = (
        _rep("omr", "Ave Verum", "Mozart", fmt=OutputFormat.PDF),
        _rep("imslp", "Ave Verum", "Mozart", fmt=OutputFormat.MIDI, remote_id="7"),
        _rep("openscore", "Ave Verum", "Mozart"),
    )
    result = _resolver().resolve(candidates)
    assert len(result.groups) == 1
    assert len(result.groups[0].group.representations) == 3


def test_distinct_composers_same_title_make_multiple_groups() -> None:
    candidates = (
        _rep("a", "Sonata", "Mozart"),
        _rep("b", "Sonata", "Beethoven"),
        _rep("c", "Sonata", "Schubert"),
    )
    result = _resolver().resolve(candidates)
    assert len(result.groups) == 3
    assert sorted(g.group.work.composer or "" for g in result.groups) == [
        "Beethoven",
        "Mozart",
        "Schubert",
    ]


def test_result_is_stable_when_input_order_changes() -> None:
    candidates = (
        _rep("omr", "Ave Verum", "Mozart", fmt=OutputFormat.PDF),
        _rep("imslp", "Ave Verum", "Mozart", remote_id="7"),
        _rep("b", "Sonata", "Beethoven", confidence=0.5),
        _rep("c", "Sonata", "Schubert", confidence=0.7),
        _rep("a", "Ave Verum", "Mozart"),
    )
    shuffled = list(candidates)
    random.Random(42).shuffle(shuffled)
    baseline = _payloads(_resolver(), candidates)
    assert _payloads(_resolver(), tuple(shuffled)) == baseline


def test_serialization_roundtrip_is_stable() -> None:
    candidates = (
        _rep("omr", "Ave Verum", "Mozart", fmt=OutputFormat.PDF),
        _rep("imslp", "Ave Verum", "Mozart", remote_id="7"),
    )
    result = _resolver().resolve(candidates)
    payload = resolved_group_payload(result.groups[0])
    serialized = canonical_json(payload)
    loaded = json.loads(serialized)
    assert canonical_json(loaded) == serialized


def test_real_change_yields_different_serialization() -> None:
    one = _resolver().resolve((_rep("omr", "Ave Verum", "Mozart"),))
    two = _resolver().resolve((_rep("omr", "Ave Verum", "Mozart"), _rep("imslp", "Ave Verum", "Mozart")))
    assert canonical_json(resolved_group_payload(one.groups[0])) != canonical_json(
        resolved_group_payload(two.groups[0])
    )


def test_serialization_does_not_depend_on_candidate_order_inside_group() -> None:
    forward = (
        _rep("omr", "Ave Verum", "Mozart", fmt=OutputFormat.PDF),
        _rep("imslp", "Ave Verum", "Mozart", remote_id="7"),
    )
    backward = (forward[1], forward[0])
    result_fwd = _resolver().resolve(forward)
    result_bwd = _resolver().resolve(backward)
    assert canonical_json(resolved_group_payload(result_fwd.groups[0])) == canonical_json(
        resolved_group_payload(result_bwd.groups[0])
    )
