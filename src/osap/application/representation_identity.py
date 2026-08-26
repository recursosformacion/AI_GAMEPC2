"""Identidad de una representación: la ficha mínima y estable de una obra.

Cada representación (de cualquier proveedor) se convierte en una ficha de
SIETE campos, con valores ya normalizados para poder compararlos por igualdad
(sin regexes en el matcher):

    RepresentationIdentity(composer, catalog, work_number, title, key,
                           movement, work_type)

El parser extrae los campos; el normalizador produce estos valores; el matcher
solo compara igualdades y aplica reglas de decisión.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from src.osap.application.metadata_normalizer import MetadataNormalizer

# Formas musicales (tipo de obra) inferibles del texto del título.
WORK_TYPES: dict[str, str] = {
    "symphony": "symphony",
    "sinfonie": "symphony",
    "concerto": "concerto",
    "sonata": "sonata",
    "mass": "mass",
    "missa": "mass",
    "messe": "mass",
    "motet": "motet",
    "motete": "motet",
    "opera": "opera",
    "cantata": "cantata",
    "requiem": "requiem",
    "nocturne": "nocturne",
    "overture": "overture",
    "quartet": "quartet",
    "trio": "trio",
    "duo": "duo",
    "lied": "lied",
    "hymn": "hymn",
    "chorale": "chorale",
    "serenade": "serenade",
    "fugue": "fugue",
    "prelude": "prelude",
    "etude": "etude",
    "waltz": "waltz",
    "toccata": "toccata",
    "variations": "variations",
}

_MOVEMENT_ROMAN = re.compile(r"\b(I{1,3}|IV|V|VI{0,3}|IX|X)\b\.?\s*([A-Za-z].*)?$")
_MOVEMENT_ARABIC = re.compile(r"\b(\d{1,2})\.\s*([A-Za-z].*)?$")
_TOKEN = re.compile(r"[a-zà-ÿ']+")


@dataclass(frozen=True)
class RepresentationIdentity:
    """La ficha de siete campos, con valores normalizados para comparar.

    ``title`` es lo que dijo la fuente (normalizado), pero NUNCA es autoritativo
    para fusionar: la identidad la dan composer + catalog (o número/clave).
    """

    composer: str | None = None
    catalog: str | None = None
    work_number: str | None = None
    title: str | None = None
    key: str | None = None
    movement: str | None = None
    work_type: str | None = None

    def __bool__(self) -> bool:
        return self.composer is not None

    def signature(self) -> str:
        """Firma derivada (consecuencia), usada solo como id estable de la obra."""
        parts = [
            p
            for p in (
                self.composer or "",
                self.catalog or "",
                self.work_number or "",
                self.key or "",
            )
            if p
        ]
        return "|".join(parts)


@lru_cache(maxsize=8192)
def build_identity(title: str, composer: str | None) -> RepresentationIdentity:
    """Normaliza un título/compositor crudos en una ficha de identidad.

    Cacheada: el matcher re-compara las mismas representaciones O(n²) veces y
    esta normalización era el cuello de botella dominante en búsquedas amplias
    (p. ej. "moz" -> 400 candidatos -> 36s de agrupación).
    """
    nm = MetadataNormalizer.normalize(title, composer)
    tokens = _TOKEN.findall(nm.normalized_title)
    work_type = next((WORK_TYPES[t] for t in tokens if t in WORK_TYPES), None)
    return RepresentationIdentity(
        composer=nm.normalized_composer,
        catalog=nm.normalized_catalog,
        work_number=nm.normalized_number,
        title=nm.normalized_title,
        key=nm.normalized_key,
        movement=_movement(title),
        work_type=work_type,
    )


def _movement(title: str) -> str | None:
    t = title.strip()
    for pattern in (_MOVEMENT_ROMAN, _MOVEMENT_ARABIC):
        match = pattern.search(t)
        if match:
            label = match.group(1).lower()
            rest = match.group(2).strip().lower() if match.group(2) else ""
            return (label + (" " + rest if rest else "")).strip()
    return None
