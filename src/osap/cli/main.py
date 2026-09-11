"""CLI entrypoint (F5.6): composición de parser y comandos."""

import sys
from dataclasses import replace

from src.osap.bootstrap.configuration import load_configuration
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire
from src.osap.cli.commands import (
    _run_catalog,
    _run_chorus_generate,
    _run_download,
    _run_search,
    _run_validate,
)
from src.osap.cli.parser import _build_parser
from src.osap.cli.resolve import _run_resolve


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return _run_validate(args)

    if args.command == "chorus-generate":
        return _run_chorus_generate(args)

    config = load_configuration()
    if getattr(args, "library", None):
        config = replace(config, library_root=args.library)
    container = wire(Container(), config)

    if args.command == "resolve":
        return _run_resolve(args, container)
    if args.command == "download":
        return _run_download(args, container)
    if args.command == "catalog":
        return _run_catalog(args, container)
    if args.command == "search":
        return _run_search(args, container)
    raise SystemExit(f"comando desconocido: {args.command}")


def entrypoint() -> None:
    sys.exit(main())



if __name__ == "__main__":
    entrypoint()
