from pathlib import Path

from src.osap.application.canonicalizer import Canonicalizer

_RULES = Path(__file__).resolve().parents[2] / "resources" / "canonical"


def _canonicalizer() -> Canonicalizer:
    return Canonicalizer(_RULES)


def test_catalogue_alias() -> None:
    result = _canonicalizer().canonicalize("K.618")
    assert result.output == "KV 618"
    assert len(result.applied) == 1
    assert result.applied[0].rule == "catalogue_aliases.yaml"
    assert result.applied[0].canonical == "KV"


def test_catalogue_variants_converge() -> None:
    canonicalizer = _canonicalizer()
    for variant in ("K.618", "K618", "KV618", "KV 618", "Köchel 618"):
        assert canonicalizer.canonicalize(variant).output == "KV 618"


def test_composer_alias() -> None:
    result = _canonicalizer().canonicalize("W. A. Mozart")
    assert result.output == "Wolfgang Amadeus Mozart"
    assert result.applied[0].rule == "composer_aliases.yaml"
    assert result.applied[0].canonical == "Wolfgang Amadeus Mozart"


def test_no_rule_found_returns_identity() -> None:
    result = _canonicalizer().canonicalize("Ave Verum Corpus")
    assert result.output == "Ave Verum Corpus"
    assert result.applied == ()


def test_multiple_rules_applied() -> None:
    result = _canonicalizer().canonicalize("W. A. Mozart, K.618")
    assert result.output == "Wolfgang Amadeus Mozart KV 618"
    assert len(result.applied) == 2
    rules = {applied.rule for applied in result.applied}
    assert rules == {"composer_aliases.yaml", "catalogue_aliases.yaml"}


def test_traceability() -> None:
    result = _canonicalizer().canonicalize("K.618")
    assert result.input == "K.618"
    assert result.normalized == "KV 618"
    assert result.output == "KV 618"
    assert len(result.rules) == 1
    assert result.rules[0].rule == "catalogue_aliases.yaml"
    assert result.rules[0].canonical == "KV"


def test_case_insensitive() -> None:
    result = _canonicalizer().canonicalize("w. a. mozart")
    assert result.output == "Wolfgang Amadeus Mozart"


def test_confidence_for_strong_alias() -> None:
    assert _canonicalizer().canonicalize("K.618").confidence == 1.0


def test_confidence_is_zero_when_no_rule() -> None:
    assert _canonicalizer().canonicalize("Ave Verum Corpus").confidence == 0.0


def test_confidence_from_rule() -> None:
    assert _canonicalizer().canonicalize("W. A. Mozart").confidence == 0.95
    assert _canonicalizer().canonicalize("JS Bach").confidence == 0.90


def test_rule_id_is_stable_and_family_scoped() -> None:
    result = _canonicalizer().canonicalize("K.618")
    assert result.applied[0].rule_id == "catalogue.kv"
    composer = _canonicalizer().canonicalize("W. A. Mozart")
    assert composer.applied[0].rule_id == "composer.wolfgang-amadeus-mozart"


def test_rule_id_independent_of_file_name() -> None:
    # rule_id is stable even if the file is renamed: it uses family + canonical slug.
    result = _canonicalizer().canonicalize("K.618")
    assert result.applied[0].rule_id != result.applied[0].rule
