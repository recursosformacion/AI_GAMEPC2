"""CLI: parser (F5.6)."""

import argparse

from src.osap.cli.requests import _parse_format
from src.osap.domain.output_format import OutputFormat


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="osap", description="OSAP — resolución de obras musicales.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser("resolve", help="Resuelve y descarga una obra musical.")
    resolve.add_argument("query", nargs="?", default=None, help="Título o texto libre (opcional si se usa --composer).")
    resolve.add_argument("--composer", default=None)
    resolve.add_argument("--genre", default=None)
    resolve.add_argument("--language", default=None)
    resolve.add_argument("--voices", nargs="*", default=[])
    resolve.add_argument("--format", dest="output_format", type=_parse_format, default=None)
    resolve.add_argument("--index", type=int, default=None, help="Índice del candidato (evita el prompt).")
    resolve.add_argument("--library", default=None)

    download = subparsers.add_parser("download", help="Descarga un candidato concreto de una obra.")
    download.add_argument("query", nargs="?", default=None)
    download.add_argument("--composer", default=None)
    download.add_argument("--format", dest="output_format", type=_parse_format, default=OutputFormat.MUSICXML)
    download.add_argument("--index", type=int, default=None)
    download.add_argument("--library", default=None)

    catalog = subparsers.add_parser("catalog", help="Lista catálogos musicales.")
    catalog_sub = catalog.add_subparsers(dest="catalog_command", required=True)

    validate = subparsers.add_parser("validate", help="Valida un MusicXML/.mxl y muestra su calidad.")
    validate.add_argument("path", help="Ruta al fichero MusicXML (.xml/.musicxml) o .mxl")
    validate.add_argument("--title", default=None, help="Título (opcional, va al Score)")
    validate.add_argument("--composer", default=None, help="Compositor (opcional, va al Score)")

    chorus = subparsers.add_parser(
        "chorus-generate",
        help="Chorus: genera un material de estudio desde un MusicXML/.mxl validado.",
    )
    chorus.add_argument("path", help="Ruta al fichero MusicXML (.xml/.musicxml) o .mxl")
    chorus.add_argument(
        "--material",
        default="exercise",
        choices=("exercise",),
        help="Tipo de material a generar (solo 'exercise' por ahora).",
    )
    chorus.add_argument("--title", default=None, help="Título (opcional, va al Score)")
    chorus.add_argument("--composer", default=None, help="Compositor (opcional, va al Score)")
    chorus.add_argument("--voice", default=None, help="Voz solicitada (opcional)")
    catalog_sub.add_parser("list", help="Lista catálogos disponibles.")
    catalog_sub.add_parser("info", help="Información de un catálogo.").add_argument("name")

    search = subparsers.add_parser("search", help="Busca obras musicales (tolerante).")
    search.add_argument("query", nargs="?", default=None)
    search.add_argument(
        "--composer",
        nargs="?",
        const="__QUERY__",
        default=None,
        help="Compositor (o flag: usa el término como compositor).",
    )
    search.add_argument("--works", action="store_true", help="Trata el término como compositor y lista sus obras.")
    search.add_argument("--all", action="store_true", help="Busca en todos los catálogos.")
    search.add_argument("--format", dest="output_format", type=_parse_format, default=None)

    return parser

