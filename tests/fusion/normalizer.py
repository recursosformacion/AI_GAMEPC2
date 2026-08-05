"""Normalizer: ¿qué valor normalizado obtengo?

Convierte un título/compositor crudos en una ficha de identidad normalizada
(RepresentationIdentity, 7 campos), para comparar por igualdad sin regexes.
"""

from __future__ import annotations

from src.osap.application.representation_identity import (
    RepresentationIdentity,
    build_identity,
)

__all__ = ["RepresentationIdentity", "build_identity"]


def normalize(title: str, composer: str | None) -> RepresentationIdentity:
    """Normaliza un título/compositor crudos en la ficha de identidad."""
    return build_identity(title, composer)
