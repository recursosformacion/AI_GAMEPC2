"""Identidad musical (prototipo para el laboratorio de fusión).

La unidad de comparación ya no es el título, sino una IDENTIDAD estructurada:

    WorkIdentity(composer_id, work_type, liturgical_form, catalog,
                 work_number, key, movement, canonical_title)

El título pasa a ser el ÚLTIMO dato (ayuda de visualización), no la base de la
identidad. La ``signature()`` es una CONSECUENCIA de la identidad (nunca al
revés): composer_id | work_type | catalog (el catálogo es el dato más fuerte).

Se distinguen tres conceptos separados:
  - work_type        : Symphony, Sonata, Concerto, Mass, Motet, Opera...
  - liturgical_form  : Ave, Kyrie, Gloria, Credo, Agnus Dei...
  - title            : lo que se muestra al usuario

Prototipo: usa solo título + compositor. Cuando el tipo requiere metadatos de
género (p. ej. "Ave Verum Corpus" es un motete, pero no lo dice el título),
``work_type`` queda vacío y su confianza baja, indicando que hace falta esa
evidencia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.application.metadata_parser import extract_metadata

# Formas musicales (tipo de obra).
WORK_TYPES: dict[str, str] = {
    "symphony": "symphony", "sinfonie": "symphony",
    "concerto": "concerto", "sonata": "sonata",
    "mass": "mass", "missa": "mass", "messe": "mass",
    "motet": "motet", "motete": "motet",
    "opera": "opera", "cantata": "cantata", "requiem": "requiem",
    "nocturne": "nocturne", "overture": "overture", "quartet": "quartet",
    "trio": "trio", "duo": "duo", "lied": "lied", "hymn": "hymn",
    "chorale": "chorale", "serenade": "serenade", "fugue": "fugue",
    "prelude": "prelude", "etude": "etude", "waltz": "waltz",
    "toccata": "toccata", "variations": "variations",
}

# Formas litúrgicas (texto, no tipo).
LITURGICAL_FORMS: dict[str, str] = {
    "ave": "ave", "kyrie": "kyrie", "gloria": "gloria", "credo": "credo",
    "agnus": "agnus dei", "sanctus": "sanctus", "benedictus": "benedictus",
    "salve": "salve", "miserere": "miserere", "magnificat": "magnificat",
    "jubilate": "jubilate", "stabat": "stabat mater", "te": "te deum",
}

_MOVEMENT_ROMAN = re.compile(r"\b(I{1,3}|IV|V|VI{0,3}|IX|X)\b\.?\s*([A-Za-z].*)?$")
_MOVEMENT_ARABIC = re.compile(r"\b(\d{1,2})\.\s*([A-Za-z].*)?$")
_TOKEN = re.compile(r"[a-zà-ÿ']+")


@dataclass(frozen=True)
class WorkIdentity:
    """Identidad musical estructurada (prototipo)."""

    composer_id: str | None
    work_type: str | None
    liturgical_form: str | None
    catalog: str | None
    catalog_raw: str | None
    work_number: str | None
    key: str | None
    movement: str | None
    canonical_title: str | None
    confidence: dict[str, float] = field(default_factory=dict)

    def signature(self) -> str:
        """Consecuencia de la identidad. El catálogo es el dato más fuerte."""
        parts = [self.composer_id or "?", self.work_type or "?"]
        if self.catalog:
            parts.append(self.catalog)
        elif self.work_number:
            parts.append(f"n{self.work_number}")
        elif self.key:
            parts.append(f"k{self.key}")
        return "|".join(parts)


def parse_identity(title: str, composer: str | None) -> WorkIdentity:
    nm = MetadataNormalizer.normalize(title, composer)
    meta = extract_metadata(title)

    tokens = _TOKEN.findall(nm.normalized_title)
    work_type = next((WORK_TYPES[t] for t in tokens if t in WORK_TYPES), None)
    liturgical = next((LITURGICAL_FORMS[t] for t in tokens if t in LITURGICAL_FORMS), None)

    catalog = nm.normalized_catalog
    catalog_compact = re.sub(r"[^a-z0-9]", "", catalog) if catalog else None
    movement = _movement(title)

    comp = MetadataNormalizer.canonical_composer(composer) if composer else None
    comp_id = _composer_id(comp) if comp else None

    confidence = {
        "composer": 1.0 if comp_id else 0.0,
        "catalog": 1.0 if catalog else 0.0,
        "type": 1.0 if work_type else 0.0,
        "number": 1.0 if nm.normalized_number else 0.0,
        "key": 1.0 if nm.normalized_key else 0.0,
        "movement": 1.0 if movement else 0.0,
    }
    return WorkIdentity(
        composer_id=comp_id,
        work_type=work_type,
        liturgical_form=liturgical,
        catalog=catalog_compact,
        catalog_raw=meta.catalogue_raw,
        work_number=nm.normalized_number,
        key=nm.normalized_key,
        movement=movement,
        canonical_title=nm.normalized_title,
        confidence=confidence,
    )


def _composer_id(canonical_name: str) -> str:
    words = [re.sub(r"[^a-z0-9]", "", w) for w in canonical_name.lower().split()]
    words = [w for w in words if w]
    if not words:
        return ""
    return "_".join(words[-1:] + words[:-1])  # apellido primero


def _movement(title: str) -> str | None:
    t = title.strip()
    for pattern in (_MOVEMENT_ROMAN, _MOVEMENT_ARABIC):
        m = pattern.search(t)
        if m:
            label = m.group(1).lower()
            rest = m.group(2).strip().lower() if m.group(2) else ""
            return (label + (" " + rest if rest else "")).strip()
    return None
