from src.osap.application.matcher import DefaultWorkMatcher
from src.osap.domain.matching import MatchField, MatchingConfig, MatchLevel, MatchResult
from src.osap.domain.value_objects import WorkId, WorkIdentifier
from src.osap.domain.work_descriptor import WorkDescriptor


def _w(
    title: str = "Ave Verum",
    composer: str | None = "Mozart",
    catalogue: str | None = None,
    key: str | None = None,
    movement: str | None = None,
    identifiers: tuple[WorkIdentifier, ...] = (),
    canonical_title: str | None = None,
    opus: str | None = None,
    creation_year: int | None = None,
    genres: tuple[str, ...] = (),
    instrumentation: tuple[str, ...] = (),
    voices: tuple[str, ...] = (),
) -> WorkDescriptor:
    return WorkDescriptor(
        work_id=WorkId("work"),
        title=title,
        composer=composer,
        catalogue_number=catalogue,
        key=key,
        movement=movement,
        identifiers=identifiers,
        canonical_title=canonical_title,
        opus=opus,
        creation_year=creation_year,
        genres=genres,
        instrumentation=instrumentation,
        voices=voices,
    )


def _matcher() -> DefaultWorkMatcher:
    return DefaultWorkMatcher(MatchingConfig())


def test_same_catalogue_is_same() -> None:
    a = _w(composer="Mozart", catalogue="KV 618")
    b = _w(composer="Mozart", catalogue="KV 618")
    result = _matcher().match(a, b)
    assert result.level is MatchLevel.SAME
    assert MatchField.CATALOGUE in result.matched_fields
    assert MatchField.CATALOGUE in result.compared_fields


def test_same_composer_and_title_is_same() -> None:
    a = _w(title="Ave Verum", composer="Mozart")
    b = _w(title="Ave Verum", composer="Mozart")
    assert _matcher().match(a, b).level is MatchLevel.SAME


def test_work_without_catalogue_still_matches() -> None:
    a = _w(composer="Mozart", title="Ave Verum", catalogue=None)
    b = _w(composer="Mozart", title="Ave Verum", catalogue=None)
    result = _matcher().match(a, b)
    assert result.level is MatchLevel.SAME
    assert MatchField.CATALOGUE not in result.compared_fields


def test_ambiguous_title_alone_is_not_same() -> None:
    a = _w(title="Sonata", composer="Mozart")
    b = _w(title="Sonata", composer="Beethoven")
    result = _matcher().match(a, b)
    assert result.level is not MatchLevel.SAME


def test_partial_title_with_unknown_composer_is_possible() -> None:
    a = _w(title="Ave Verum", composer=None)
    b = _w(title="Ave Verum Corpus", composer=None)
    result = _matcher().match(a, b)
    assert result.level is MatchLevel.POSSIBLE
    assert MatchField.TITLE in result.compared_fields
    assert MatchField.TITLE not in result.matched_fields  # partial is not a perfect match


def test_canonicalized_alias_is_same() -> None:
    a = _w(composer="Mozart", canonical_title="Ave Verum Corpus")
    b = _w(composer="Mozart", canonical_title="Ave Verum Corpus")
    assert _matcher().match(a, b).level is MatchLevel.SAME


def test_transposition_does_not_break_match() -> None:
    a = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum", key="C")
    b = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum", key="D")
    result = _matcher().match(a, b)
    assert result.level is MatchLevel.SAME
    assert MatchField.KEY in result.mismatched_fields


def test_shared_work_authority_is_same() -> None:
    a = _w(composer="Other", title="Something Else", identifiers=(WorkIdentifier("wikidata", "Q123"),))
    b = _w(composer="Another", title="Yet Another", identifiers=(WorkIdentifier("wikidata", "Q123"),))
    result = _matcher().match(a, b)
    assert result.level is MatchLevel.SAME
    assert MatchField.WORK_AUTHORITY in result.matched_fields


def test_distinct_works_are_different() -> None:
    a = _w(title="Ave Verum", composer="Mozart")
    b = _w(title="Symphony 40", composer="Beethoven")
    assert _matcher().match(a, b).level is MatchLevel.DIFFERENT


def test_symmetry() -> None:
    matcher = _matcher()
    a = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum", key="C")
    b = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum Corpus", key="D")
    forward = matcher.match(a, b)
    backward = matcher.match(b, a)
    assert forward.level is backward.level
    assert forward.match_score == backward.match_score
    assert set(forward.compared_fields) == set(backward.compared_fields)


def test_determinism() -> None:
    matcher = _matcher()
    a = _w(composer="Mozart", catalogue="KV 618")
    b = _w(composer="Mozart", catalogue="KV 618")
    first = matcher.match(a, b)
    second = matcher.match(a, b)
    assert first == second
    assert first.match_score == second.match_score


def test_work_descriptors_are_not_modified() -> None:
    matcher = _matcher()
    a = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum")
    b = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum")
    a_original = (a.composer, a.catalogue_number, a.title)
    b_original = (b.composer, b.catalogue_number, b.title)
    matcher.match(a, b)
    assert (a.composer, a.catalogue_number, a.title) == a_original
    assert (b.composer, b.catalogue_number, b.title) == b_original


def test_absent_fields_do_not_penalize() -> None:
    full = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum")
    partial = _w(composer="Mozart", title="Ave Verum")
    result = _matcher().match(full, partial)
    assert result.level is MatchLevel.SAME
    assert MatchField.CATALOGUE not in result.compared_fields


def test_compared_fields_reflect_what_was_compared() -> None:
    a = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum")
    b = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum")
    result = _matcher().match(a, b)
    assert set(result.compared_fields) == {MatchField.CATALOGUE, MatchField.COMPOSER, MatchField.TITLE}


def test_match_reason_is_generated() -> None:
    a = _w(composer="Mozart", catalogue="KV 618")
    b = _w(composer="Mozart", catalogue="KV 618")
    result = _matcher().match(a, b)
    catalogue_reason = next(r for r in result.reasons if r.field is MatchField.CATALOGUE)
    assert catalogue_reason.field_score == 1.0
    assert catalogue_reason.left == catalogue_reason.right == "kv 618"
    assert isinstance(result, MatchResult)


def test_title_partial_score_is_less_than_exact() -> None:
    matcher = _matcher()
    exact = matcher.match(_w(composer="Mozart", title="Ave Verum"), _w(composer="Mozart", title="Ave Verum"))
    partial = matcher.match(
        _w(composer="Mozart", title="Ave Verum"), _w(composer="Mozart", title="Ave Verum Corpus")
    )
    exact_title = next(r for r in exact.reasons if r.field is MatchField.TITLE)
    partial_title = next(r for r in partial.reasons if r.field is MatchField.TITLE)
    assert exact_title.field_score == 1.0
    assert partial_title.field_score == 0.6
    assert partial.level is MatchLevel.SAME  # same composer + partial title is still same work


def test_skipped_field_has_no_reason() -> None:
    a = _w(composer="Mozart", title="Ave Verum")
    b = _w(composer="Mozart", title="Ave Verum")
    result = _matcher().match(a, b)
    assert MatchField.CATALOGUE not in result.compared_fields
    assert all(r.field is not MatchField.CATALOGUE for r in result.reasons)


def test_catalogue_contradiction_is_different() -> None:
    a = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum")
    b = _w(composer="Mozart", catalogue="KV 620", title="Ave Verum")
    result = _matcher().match(a, b)
    assert result.level is MatchLevel.DIFFERENT
    assert MatchField.CATALOGUE in result.mismatched_fields


def test_canonicalized_catalogue_variants_are_same() -> None:
    # After the Canonicalizer, KV618/K618/K.618 all reach the matcher as "KV 618".
    a = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum")
    b = _w(composer="Mozart", catalogue="KV 618", title="Ave Verum")
    assert _matcher().match(a, b).level is MatchLevel.SAME


def test_same_work_by_composer_and_title_when_opus_absent() -> None:
    # Op. 67 and "Symphony No. 5" are the same work; composer + title decide.
    a = _w(composer="Beethoven", opus="Op. 67", title="Symphony No. 5")
    b = _w(composer="Beethoven", title="Symphony No. 5", opus=None)
    result = _matcher().match(a, b)
    assert result.level is MatchLevel.SAME
