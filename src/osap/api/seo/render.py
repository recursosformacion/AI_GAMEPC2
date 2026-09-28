"""Renderer Jinja2 de las páginas públicas SEO.

Carga las plantillas de `src/osap/api/templates/` y expone funciones tipadas. El entorno
se construye una sola vez (autoescape activado).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

if TYPE_CHECKING:
    from src.osap.api.seo.views import PersonView, WorkView

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_ENV: Environment | None = None


def _env() -> Environment:
    global _ENV
    if _ENV is None:
        _ENV = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _ENV


def render_work(view: WorkView) -> str:
    return _env().get_template("work.html").render(view=view, canonical_url=view.canonical_url)


def render_person(view: PersonView) -> str:
    return _env().get_template("composer.html").render(view=view, canonical_url=view.canonical_url)


def render_not_found() -> str:
    return _env().get_template("not_found.html").render()
