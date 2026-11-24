from script.index_works import _disambiguated_tk


def test_disambiguates_numbered_works() -> None:
    assert (
        _disambiguated_tk("violin concerto", "Violin Concerto No.1 in F major")
        == "violin concerto 1"
    )
    assert (
        _disambiguated_tk("violin concerto", "Violin Concerto No.3 in B-flat major")
        == "violin concerto 3"
    )


def test_keeps_key_without_numbers() -> None:
    assert _disambiguated_tk("ave verum corpus", "Ave Verum Corpus") == "ave verum corpus"
