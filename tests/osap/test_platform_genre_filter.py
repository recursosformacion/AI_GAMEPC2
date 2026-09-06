"""Filtro de género en el Estudio — mapeo nombre→genre_id, search_model y propagación."""

from src.osap.api.platform import _STUDIO_GENRE_OPTIONS, _genre_id_for_name, _studio_genre_names
from src.osap.domain.resolve_request import ResolveRequest, ResolveRequestBuilder
from src.osap.domain.search_request import SearchRequest


def test_genre_catalog_mirrors_040_seed() -> None:
    """El espejo estático del Estudio coincide con la semilla 040 de osap-storage."""
    assert len(_STUDIO_GENRE_OPTIONS) == 12
    assert _STUDIO_GENRE_OPTIONS[0] == (1, "Música Clásica / Docta")
    assert _STUDIO_GENRE_OPTIONS[11] == (12, "Música Escénica y Aplicada")
    ids = [genre_id for genre_id, _ in _STUDIO_GENRE_OPTIONS]
    assert ids == list(range(1, 13))


def test_studio_genre_names_fuente_del_bloque() -> None:
    """El bloque Género del search_model se alimenta de los 12 nombres visibles."""
    names = _studio_genre_names()
    assert len(names) == 12
    assert names[0] == "Música Clásica / Docta"
    assert all(_genre_id_for_name(name) is not None for name in names)


def test_genre_id_for_name_resuelve_macrofamilia() -> None:
    assert _genre_id_for_name("Música Clásica / Docta") == 1
    assert _genre_id_for_name("Jazz y Blues") == 4
    assert _genre_id_for_name("  Pop  ") == 6
    assert _genre_id_for_name("No existe") is None


def test_resolve_request_propaga_genre_ids() -> None:
    req = (
        ResolveRequestBuilder()
        .text("mozart")
        .genre_ids(1, 5)
        .build()
    )
    assert req.genre_ids == (1, 5)
    derived = SearchRequest.from_resolve(req)
    assert derived.genre_ids == (1, 5)
    assert derived.searches_by_genre is True


def test_resolve_request_sin_genre_ids() -> None:
    req = ResolveRequest(query="mozart")
    assert req.genre_ids == ()
    derived = SearchRequest.from_resolve(req)
    assert derived.genre_ids == ()
    assert derived.searches_by_genre is False
