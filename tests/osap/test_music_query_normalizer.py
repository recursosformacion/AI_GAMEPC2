from src.osap.domain.music_query_normalizer import MusicQueryNormalizer


class TestMusicQueryNormalizer:
    def test_accents_and_case(self) -> None:
        assert MusicQueryNormalizer.normalize("Cançó de Comiat") == "canco de comiat"
        assert MusicQueryNormalizer.normalize("Noctúrnő") == "nocturno"
        assert MusicQueryNormalizer.normalize("MOZART") == "mozart"

    def test_tokens(self) -> None:
        assert MusicQueryNormalizer.tokens("Ave Maria") == ["ave", "maria"]

    def test_matches_ignores_accents(self) -> None:
        assert MusicQueryNormalizer.matches("Cançó de Comiat", "Canco de Comiat") is True
        assert MusicQueryNormalizer.matches("Schubert, Franz", "Schubert") is True
        assert MusicQueryNormalizer.matches("Nocturne", "nocturno") is False

    def test_partial_words(self) -> None:
        assert MusicQueryNormalizer.matches("Die Sterne, D.939", "Sterne") is True
