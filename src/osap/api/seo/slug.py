"""Slugs SEO deterministas para las URLs públicas de compositor y obra.

El slug es descriptivo (palabras clave), pero NUNCA es la identidad: la identidad viaja
siempre en el id estable de la URL (`/obra/index-123/<slug>`), de modo que un cambio de
título solo provoca un redirect 301 y no rompe el enlace permanente.
"""

from __future__ import annotations

import re
import unicodedata

_MAX_SLUG = 80
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# Guiones/dashes unicode (en-dash, em-dash, minus…) no descomponen a ASCII con NFKD:
# se convierten en separador antes de normalizar para no pegar las palabras.
_DASHES = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]")
# Ligaduras y letras que NFKD no descompone a ASCII (Œ, Æ, ß, Ø…): sin esto se perderían
# ("Œuvre" -> "uvre"). Se transliteran antes de normalizar.
_TRANSLITERATIONS = str.maketrans(
    {
        "\u0153": "oe",
        "\u0152": "OE",
        "\u00e6": "ae",
        "\u00c6": "AE",
        "\u00df": "ss",
        "\u00f8": "o",
        "\u00d8": "O",
        "\u00fe": "th",
        "\u00de": "TH",
        "\u0111": "d",
        "\u0110": "D",
        "\u0142": "l",
        "\u0141": "L",
    }
)


def slugify(text: str) -> str:
    """Minúsculas, sin acentos y con separadores normalizados a guiones."""
    prepped = _DASHES.sub(" ", (text or "").translate(_TRANSLITERATIONS))
    normalized = unicodedata.normalize("NFKD", prepped)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_ALNUM.sub("-", ascii_text).strip("-")
    return slug[:_MAX_SLUG].strip("-")


def work_slug(title: str) -> str:
    """Slug de una obra; nunca vacío (fallback estable "obra")."""
    return slugify(title) or "obra"


def person_slug(name: str) -> str:
    """Slug de una persona; nunca vacío (fallback estable "compositor")."""
    return slugify(name) or "compositor"


def normalize_work_id(work_id: str) -> str | None:
    """Normaliza el id de obra a su forma canónica `index-<n>`.

    Acepta tanto `index-123` (id expuesto por la app) como `123` (id de `index_works`).
    Devuelve `None` si no es un id numérico de obra.
    """
    raw = work_id[len("index-") :] if work_id.startswith("index-") else work_id
    if not raw.isdigit():
        return None
    return f"index-{int(raw)}"
