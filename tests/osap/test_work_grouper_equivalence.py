"""Equivalencia entre el agrupador con bloqueo (rápido) y la referencia O(n²).

El agrupador indexa cluster por claves necesarias (catálogo, número, bigramas de título)
para no comparar todos contra todos. Este test comprueba que **produce exactamente las
mismas particiones** que la implementación de referencia en un conjunto variado de casos
(catálogos, números, títulos genéricos, anónimos, compositores distintos…).
"""

from __future__ import annotations

from src.osap.application.work_grouper import WorkGrouper
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor


def _cand(ident: str, title: str, composer: str | None, provider: str = "omr") -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(ident),
        work_descriptor=WorkDescriptor(work_id=WorkId(ident), title=title, composer=composer),
        provider_id=ProviderId(provider),
        format=OutputFormat.MUSICXML,
        origin="test",
        confidence=Confidence(0.9),
    )


def _dataset() -> tuple[CandidateRepresentation, ...]:
    items: list[CandidateRepresentation] = []
    # Mismo catálogo, compositores distintos en la forma (debe fusionar por catálogo).
    items += [
        _cand("a1", "Ave Verum, KV 618", "Mozart"),
        _cand("a2", "Ave Verum Corpus K 618 - Wolfgang Amadeus Mozart", "Wolfgang Amadeus Mozart"),
        _cand("a3", "Ave verum corpus, cor, pf, KV 618, 1944", "Wolfgang Amadeus Mozart", "imslp"),
    ]
    # Mismo compositor + número + clave, títulos distintos.
    items += [
        _cand("b1", "Sonata in C major, No. 5", "Beethoven"),
        _cand("b2", "Sonata No. 5 in C major", "Ludwig van Beethoven"),
    ]
    # Título muy parecido, mismo compositor, sin catálogo.
    items += [
        _cand("c1", "Ave Verum Corpus", "Mozart"),
        _cand("c2", "Ave Verum Corpus", "Mozart", "cpdl"),
        _cand("c3", "Ave Verum", "Mozart"),
    ]
    # Preludios de Chopin: no deben fusionarse (título genérico sin anclaje).
    items += [
        _cand("d1", "Prelude in E-flat minor, Op. 28 No. 24", "Chopin"),
        _cand("d2", "Prelude in G major, Op. 28 No. 3", "Chopin"),
        _cand("d3", "Prelude in A major, Op. 28 No. 7", "Frédéric Chopin"),
    ]
    # Compositor específico distinto: nunca fusionan entre sí.
    items += [
        _cand("e1", "Salve Regina", "Palestrina"),
        _cand("e2", "Salve Regina", "Victoria"),
    ]
    # Anónimos/sin dato con mismo título.
    items += [
        _cand("f1", "Alma Redemptoris Mater", None),
        _cand("f2", "Alma Redemptoris Mater", "Anonymous"),
        _cand("f3", "Alma redemptoris mater", "Anonymous", "mutopia"),
    ]
    # Título de un solo token (bloqueo por token).
    items += [
        _cand("g1", "Sicut", "Anonymous"),
        _cand("g2", "Sicut", "Anonymous"),
    ]
    # Bach: muchas obras con token común ("bwv") y números distintos → no deben fusionar.
    items += [
        _cand(f"h{i}", f"BWV {100 + i} Choral", "Johann Sebastian Bach") for i in range(30)
    ]
    return tuple(items)


def _partition(groups: tuple[object, ...]) -> set[frozenset[str]]:
    return {
        frozenset(str(r.candidate_id.value) for r in group.representations)  # type: ignore[attr-defined]
        for group in groups
    }


def test_bloqueo_equivale_a_referencia() -> None:
    grouper = WorkGrouper()
    data = _dataset()
    fast = grouper.group(data)
    reference = grouper.group_reference(data)
    assert _partition(fast) == _partition(reference)
    # Y el bloqueo no deja grupos vacíos ni pierde candidatos.
    assert sum(len(g.representations) for g in fast) == len(data)
