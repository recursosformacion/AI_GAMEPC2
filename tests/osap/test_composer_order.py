from src.osap.application.metadata_normalizer import MetadataNormalizer as N


def test_surname_first_composer_matches_given_first():
    assert N.comparison_composer("Mozart, Wolfgang Amadeus") == N.comparison_composer(
        "Wolfgang Amadeus Mozart"
    )
    assert N.comparison_title("Ave Verum Corpus", "Mozart, Wolfgang Amadeus") == (
        N.comparison_title("Mozart: Ave Verum Corpus K. 618", "Wolfgang Amadeus Mozart")
    )


def test_composer_is_extracted_from_an_anonymous_title():
    from src.osap.application.metadata_normalizer import MetadataNormalizer as N

    assert N.composer_from_title("Ave Verum-Mozart-voces - Copie") == "Wolfgang Amadeus Mozart"
    assert N.composer_from_title("Ave Verum") is None
