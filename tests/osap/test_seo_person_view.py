from __future__ import annotations

import json

from src.osap.api.seo.views import build_person_view


def test_ficha_sin_biografia_genera_contenido_catalografico_unico() -> None:
    detail = {
        "id": "person-1",
        "name": "Ana Pérez",
        "visible": True,
        "birth_year": "1900",
        "death_year": "1980",
        "nationality": "España",
        "biography_summary": None,
        "biography_key_fact": None,
        "identifiers": [
            {"id_type": "viaf", "id_value": "12345"},
            {"id_type": "imslp", "id_value": "Category:Pérez,_Ana"},
        ],
        "biography_references": "CPDL (ChoralWiki); Wikipedia",
        "image_url": "https://cdn.example.com/ana.jpg",
    }
    works = {
        "items": [
            {"work_id": 7, "title": "Misa de Navidad", "catalogue": "AP 1"},
            {"work_id": 8, "title": "Ave maris stella", "catalogue": None},
        ],
        "total": 2,
    }
    view = build_person_view(detail, works)

    assert view.has_biography is False
    assert "Ana Pérez (1900–1980)" in view.intro
    assert "2 obras" in view.intro
    assert "Misa de Navidad" in view.intro
    assert "Ficha catalográfica" in view.catalog_note
    assert view.description.startswith("Ana Pérez (1900–1980): 2 obras")
    assert [link.label for link in view.authority_links] == ["VIAF", "IMSLP"]
    assert view.authority_links[0].url == "https://viaf.org/viaf/12345"
    assert [ref.label for ref in view.reference_links] == ["CPDL (ChoralWiki)", "Wikipedia"]

    payload = json.loads(view.json_ld)
    person = next(node for node in payload["@graph"] if node["@type"] == "Person")
    assert person["description"] == view.intro
    assert person["image"] == "https://cdn.example.com/ana.jpg"
    assert "https://viaf.org/viaf/12345" in person["sameAs"]


def test_imagen_de_wikidata_sin_esquema_se_normaliza_a_commons() -> None:
    detail = {
        "id": "person-3",
        "name": "Josef Leopold Zvonař",
        "visible": True,
        "image_url": "Josef%20Leopold%20Zvonar%201882%20Vilimek.png",
    }
    view = build_person_view(detail, {"items": [], "total": 0})
    assert view.image_url == (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        "Josef%20Leopold%20Zvonar%201882%20Vilimek.png"
    )
    payload = json.loads(view.json_ld)
    person = next(node for node in payload["@graph"] if node["@type"] == "Person")
    assert person["image"] == view.image_url


def test_ficha_con_biografia_usa_el_resumen_y_conserva_datos_de_autoridad() -> None:
    detail = {
        "id": "person-2",
        "name": "Clara Schumann",
        "visible": True,
        "biography_summary": "Compositora y pianista alemana.",
        "nationality": "Alemania",
        "identifiers": [{"id_type": "wikidata_qid", "id_value": "Q76327"}],
    }
    view = build_person_view(detail, {"items": [], "total": 0})

    assert view.has_biography is True
    assert view.intro == "Compositora y pianista alemana."
    assert view.authority_links[0].url == "https://www.wikidata.org/wiki/Q76327"
    payload = json.loads(view.json_ld)
    person = next(node for node in payload["@graph"] if node["@type"] == "Person")
    assert person["description"] == "Compositora y pianista alemana."
    assert person["nationality"] == "Alemania"
