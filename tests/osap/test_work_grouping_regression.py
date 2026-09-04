"""Regresión de fusión por fallback de título (WorkGroupingMatcher).

Caso Chopin: tres Preludios del Op. 28 con catálogo/número/clave distintos NO deben
fusionarse aunque el título reducido coincida en 'prelude'. La fusión por título solo
aplica con título específico (>=3 tokens) o cuando no hay contradicción estructurada.
"""

from src.osap.application.work_grouping_matcher import MergeVerdict, WorkGroupingMatcher
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor

_matcher = WorkGroupingMatcher()


def _cand(title: str, composer: str | None) -> CandidateRepresentation:
    return CandidateRepresentation(
        candidate_id=CandidateId(title),
        work_descriptor=WorkDescriptor(work_id=WorkId(title), title=title, composer=composer),
        provider_id=ProviderId("omr"),
        format=OutputFormat.MUSICXML,
        origin="test",
        confidence=Confidence(0.9),
    )


def test_chopin_preludes_not_merged() -> None:
    a = _cand("Prelude in E-flat minor", "Chopin")
    b = _cand("Chopin Prelude Op. 28 No. 24", "Chopin")
    c = _cand("Frédéric Chopin: Prelude in G major Op.28 No.3", "Frédéric Chopin")

    for x, y in ((a, b), (a, c), (b, c)):
        d = _matcher.compare(x, y)
        assert d.decision is MergeVerdict.NOT_MERGED, f"fusionó: {x.work_descriptor.title} vs {y.work_descriptor.title}"


def test_same_catalog_merges() -> None:
    a = _cand("Ave Verum, KV 618", "Mozart")
    b = _cand("Ave Verum Corpus K 618 - Wolfgang Amadeus Mozart", "Wolfgang Amadeus Mozart")
    d = _matcher.compare(a, b)
    assert d.decision is MergeVerdict.MERGED


def test_ave_verum_corpus_specific_title_merges_without_catalog() -> None:
    a = _cand("Ave Verum Corpus", "Mozart")
    b = _cand("Ave Verum Corpus, K. 618", "Mozart")
    d = _matcher.compare(a, b)
    assert d.decision is MergeVerdict.MERGED


# ---------------------------------------------------------------------------
# Regresión de los tres grupos reales de "Ave Verum Corpus"
# ---------------------------------------------------------------------------

from src.osap.application.work_merge_service import WorkMergeService  # noqa: E402

_G1 = [
    ("g1a", "Ave verum corpus, cor, pf, KV 618, 1944", "Wolfgang Amadeus Mozart"),
    ("g1b", "Ave verum, vl (3), vlc, KV 618, 1943", "Wolfgang Amadeus Mozart"),
    ("g1c", "Ave verum corpus, Coro, strings, KV 618, 1930", "Wolfgang Amadeus Mozart"),
    ("g1d", "Ave verum corpus KV 618 - Wolfgang Amadeus Mozart", "Wolfgang Amadeus Mozart"),
]
_G2 = [
    ("g2a", "Ave Verum Corpus", None),
    ("g2b", "Ave verum corpus - Anonymous (Gregorian chant)", "Anonymous"),
    ("g2c", "Ave verum corpus - Gaspar van Weerbeke", "Gaspar van Weerbeke"),
]
_G3 = [
    ("g3a", "Ave Verum", "Wolfgang Amadeus Mozart"),
    ("g3b", "Ave Verum Corpus - Mozart TTBB", "Wolfgang Amadeus Mozart"),
    ("g3c", "Ave verum corpus KV 618 - Wolfgang Amadeus Mozart", "Wolfgang Amadeus Mozart"),
    ("g3d", "Ave Verum Corpus W. A. Mozart (K. 618)", "W. A. Mozart"),
    ("g3e", "Ave verum corpus - Vocal Score", "Wolfgang Amadeus Mozart"),
]

_ALL = _G1 + _G2 + _G3


def _titles() -> dict[str, str]:
    return {key: title for key, title, _composer in _ALL}


def _group_members(groups: object) -> list[set[str]]:
    return [
        {c.work_descriptor.title for c in g.representations}  # type: ignore[union-attr]
        for g in groups  # type: ignore[union-attr]
    ]


def _cluster_of(key: str, groups: object) -> set[str]:
    target = _titles()[key]
    for members in _group_members(groups):
        if target in members:
            return members
    return set()


def _run_groups() -> object:
    return WorkMergeService().group(tuple(_cand(title, composer) for _k, title, composer in _ALL))


def test_regresion_kv618_mozart_un_grupo() -> None:
    """Los títulos Mozart con KV/K. 618 deben acabar en UNA única obra."""
    groups = _run_groups()
    kv_keys = {"g1a", "g1b", "g1c", "g1d", "g3c", "g3d"}
    clusters = {frozenset(_cluster_of(k, groups)) for k in kv_keys}
    assert len(clusters) == 1, f"KV618 partido en varios grupos: {clusters}"
    cluster = next(iter(clusters))
    expected_titles = {_titles()[k] for k in kv_keys}
    assert expected_titles <= cluster


def test_regresion_weerbeke_no_se_mezcla() -> None:
    groups = _run_groups()
    weerbeke = _cluster_of("g2c", groups)
    assert any("Weerbeke" in t for t in weerbeke)
    assert "Ave Verum Corpus" not in weerbeke
    assert _cluster_of("g2b", groups) != weerbeke
    assert _cluster_of("g1d", groups) != weerbeke


def test_regresion_anonymos_no_comodin() -> None:
    """'Anonymous'/sin atribución no se fusiona con una atribución concreta."""
    mozart = _cand("Ave Verum Corpus", "Wolfgang Amadeus Mozart")
    anonymous = _cand("Ave Verum Corpus", "Anonymous")
    weerbeke = _cand("Ave Verum Corpus", "Gaspar van Weerbeke")
    assert _matcher.compare(mozart, anonymous).decision is MergeVerdict.NOT_MERGED
    assert _matcher.compare(weerbeke, anonymous).decision is MergeVerdict.NOT_MERGED
    assert _matcher.compare(mozart, weerbeke).decision is MergeVerdict.NOT_MERGED


def test_regresion_chant_anonimo_comparte_grupo() -> None:
    """Las versiones anónimas del canto gregoriano pueden agruparse entre sí."""
    d = _matcher.compare(
        _cand("Ave Verum Corpus", None),
        _cand("Ave verum corpus - Anonymous (Gregorian chant)", "Anonymous"),
    )
    assert d.decision is MergeVerdict.MERGED


def test_no_fusion_solo_por_titulo_sin_compositor() -> None:
    """Ausencia de compositor en un lado no sirve de comodín para una atribución concreta."""
    d = _matcher.compare(_cand("Ave Verum Corpus", None), _cand("Ave Verum Corpus", "Wolfgang Amadeus Mozart"))
    assert d.decision is MergeVerdict.NOT_MERGED
