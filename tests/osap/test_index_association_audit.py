from script.audit_index_associations import _number_conflict


def test_audit_detects_different_explicit_work_numbers() -> None:
    assert _number_conflict(
        "Violin Concerto No.3 in B-flat major",
        "Violin Concerto No.1 in F major",
    ) == ("3", "1")


def test_audit_accepts_same_work_number() -> None:
    assert _number_conflict(
        "Violin Concerto No.3 in B-flat major",
        "Violin Concerto No.3 in B-flat major (parts)",
    ) == (None, None)


def test_audit_does_not_infer_conflict_when_one_title_has_no_number() -> None:
    assert _number_conflict(
        "Ave Verum Corpus",
        "Ave Verum Corpus a 4",
    ) == (None, None)
