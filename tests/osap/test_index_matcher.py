"""Tests del matcher de obras del builder de índice (antirregresión del bug de "cubos").

Invariante de agrupación: los tokens del compositor embebidos en el título NO cuentan
como palabras significativas del título. Sin esto, "Frédéric Chopin: Prelude X" y
"Frédéric Chopin: Prelude Y" reducen ambas a {ric, chopin} y se fusionan en una obra.
"""

from script.index_works import (
    _shares_significant_token,
    _significant_tokens,
    _tokens_subset,
)

CHOPIN = "Frédéric Chopin"


def test_compositor_no_cuenta_como_palabra_del_titulo() -> None:
    toks = _significant_tokens(f"{CHOPIN}: Prelude in A major Op.28 No.7", CHOPIN)
    assert "chopin" not in toks
    assert "ric" not in toks
    # Solo quedaba "prelude", que es genérico -> sin tokens propios.
    assert toks == set()


def test_chopin_distintas_obras_no_son_subconjunto() -> None:
    a = f"{CHOPIN}: Prelude in A major Op.28 No.7"
    b = f"{CHOPIN}: Prelude in B major Op.28 No.11"
    assert _tokens_subset(a, b, CHOPIN) is False


def test_chopin_etude_y_prelude_no_comparten() -> None:
    a = "Chopin Frédéric Études Op. 10 3. Étude in F major The Horseman"
    b = f"{CHOPIN}: Prelude in A major Op.28 No.7"
    assert _shares_significant_token(a, b, CHOPIN) is False


def test_anclaje_legitimo_mozart_sigue_funcionando() -> None:
    """Un título corto sin catálogo debe anclarse a la obra con catálogo (Mozart)."""
    a = "Ave Verum Corpus - Mozart TTBB"
    b = "Mozart: Ave Verum Corpus K. 618"
    moz = "Wolfgang Amadeus Mozart"
    assert _tokens_subset(a, b, moz) is True


def test_sin_compositor_no_cambia_el_comportamiento_de_titulos_propios() -> None:
    assert _tokens_subset("Ave Verum Corpus", "Ave Verum Corpus a 4") is True
