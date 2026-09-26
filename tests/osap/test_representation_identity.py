"""Identidad de deduplicación de representaciones (edición/recurso vs URL)."""

from src.osap.api.contracts import RepresentationInfo
from src.osap.api.platform.search import _rep_identity_key


def _rep(**over: object) -> RepresentationInfo:
    data: dict[str, object] = {
        "id": "r1",
        "provider": "cpdl",
        "format": "pdf",
        "confidence": 0.7,
        "url": "https://www.cpdl.org/wiki/x.pdf",
        "metadata": None,
    }
    data.update(over)
    return RepresentationInfo(**data)  # type: ignore[arg-type]


def test_resource_id_tiene_prioridad() -> None:
    key = _rep_identity_key(_rep(metadata={"resource_id": 392025, "source_rep_id": "301"}))
    assert key == ("cpdl", "rid:392025")


def test_sin_resource_usa_edicion_y_formato() -> None:
    key = _rep_identity_key(_rep(metadata={"source_rep_id": "301"}, format="midi"))
    assert key == ("cpdl", "src:301", "midi")


def test_sin_identidad_cae_a_url() -> None:
    key = _rep_identity_key(_rep(provider="omr", metadata=None))
    assert key == ("omr", "https://www.cpdl.org/wiki/x.pdf")


def test_ediciones_cpdl_con_misma_url_no_colisionan() -> None:
    """CPDL 301 y 302 comparten URL: la identidad de recurso las mantiene separadas."""
    a = _rep_identity_key(_rep(metadata={"resource_id": 392025, "source_rep_id": "301"}))
    b = _rep_identity_key(_rep(metadata={"resource_id": 392034, "source_rep_id": "302"}))
    assert a != b
