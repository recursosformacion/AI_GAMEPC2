"""Pruebas del Léxico musical y su comportamiento de clasificación."""

from pathlib import Path

from src.osap.application.lexicon import Lexicon

_LEXICON = Path(__file__).resolve().parents[2] / "lexicon"


class TestLexicon:
    def test_forms_are_identity(self) -> None:
        lex = Lexicon(_LEXICON, debug=False)
        result = lex.classify("Symphony No.40")
        assert "symphony" in result.identity

    def test_movements_are_sublevel(self) -> None:
        lex = Lexicon(_LEXICON, debug=False)
        result = lex.classify("Symphony No.40 II. Andante")
        assert "andante" in result.movement

    def test_instruments_are_descriptive(self) -> None:
        lex = Lexicon(_LEXICON, debug=False)
        result = lex.classify("Clarinet Concerto in A")
        assert "clarinet" in result.descriptive

    def test_work_number(self) -> None:
        lex = Lexicon(_LEXICON, debug=False)
        assert lex.classify("Symphony No.40").work_number == "40"

    def test_editorial_words_are_skipped(self) -> None:
        lex = Lexicon(_LEXICON, debug=False)
        for word in ("draft", "complete", "reproduction", "wip", "facsimile", "accurate"):
            result = lex.classify(f"Ave Verum Corpus {word}")
            assert word not in result.unknowns, f"{word} no debería ser desconocido"

    def test_proper_names_are_skipped(self) -> None:
        lex = Lexicon(_LEXICON, debug=False)
        result = lex.classify("Mozart flute concerto no.1 in G major kv131")
        assert "mozart" not in result.unknowns

    def test_numbering_is_skipped(self) -> None:
        lex = Lexicon(_LEXICON, debug=False)
        for word in ("ii", "iii", "iv", "v", "vi", "vii", "1st", "2nd", "3rd", "4th"):
            result = lex.classify(f"Piece {word}")
            assert word not in result.unknowns, f"{word} no debería ser desconocido"

    def test_debug_registers_unknowns_without_duplicates(self, tmp_path: Path) -> None:
        lex = Lexicon(_LEXICON, debug=True)
        lex.path = tmp_path
        lex.classify("Ave Verum Corpus xyzdori")
        lex.classify("Ave Verum Corpus xyzdori")
        target = tmp_path / "sinAsignar.yaml"
        assert target.exists()
        assert lex.new_unknowns == 1  # segunda pasada: sin duplicados

    def test_full_phrases_are_overcome(self) -> None:
        # Las frases completas se reconocen como UNIDAD: ninguna de sus palabras
        # debe quedar como desconocida.
        lex = Lexicon(_LEXICON, debug=False)
        for title in (
            "Eine Kleine Nachtmusik",
            "Die Zauberflöte",
            "Le Nozze di Figaro",
            "Così fan tutte",
            "Stabat Mater",
            "Dies Irae",
        ):
            result = lex.classify(title)
            assert not result.unknowns, f"{title}: desconocidos inesperados {result.unknowns}"

    def test_notes_are_classified_not_ignored(self) -> None:
        lex = Lexicon(_LEXICON, debug=False)
        result = lex.classify("Symphony No.40 in G major")
        assert "g" in result.descriptive
        assert "g" not in result.unknowns

    def test_performing_forces_are_descriptive(self) -> None:
        lex = Lexicon(_LEXICON, debug=False)
        result = lex.classify("Ave Verum Corpus for SATB choir")
        assert "satb" in result.descriptive
