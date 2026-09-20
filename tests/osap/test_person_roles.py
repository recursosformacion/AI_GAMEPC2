"""Tests del mapeo de roles de persona (modelo nuevo `persons`)."""

import pytest

from src.osap.domain.person_roles import (
    ROLE_IDS,
    parse_roles,
    person_has_role,
    role_ids,
    role_names,
)


def test_parse_roles_default_es_composer() -> None:
    assert parse_roles(None) == ("composer",)
    assert parse_roles("") == ("composer",)


def test_parse_roles_varios_y_normalizacion() -> None:
    assert parse_roles("composer,arranger") == ("composer", "arranger")
    assert parse_roles(" Composer , ARRANGER , composer ") == ("composer", "arranger")
    assert parse_roles(["performer", "editor"]) == ("performer", "editor")


def test_parse_roles_desconocido_falla() -> None:
    with pytest.raises(ValueError, match="desconocido"):
        parse_roles("composer,pianist")


def test_role_ids_y_nombres() -> None:
    assert role_ids(("composer", "arranger")) == (1, 3)
    assert role_names([1, 3, 999, "10"]) == ["composer", "arranger", "performer"]
    assert ROLE_IDS["editor"] == 6


def test_person_has_role_por_nombre_o_id() -> None:
    assert person_has_role({"roles": ["composer"]}, "composer")
    assert person_has_role({"role_ids": [1, 3]}, "arranger")
    assert not person_has_role({"roles": ["performer"]}, "composer")
