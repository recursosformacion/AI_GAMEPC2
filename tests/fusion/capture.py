#!/usr/bin/env python3
"""capture.py — Guarda una consulta real de OSAP como golden dataset.

Convierte una consulta (p. ej. `osap resolve --composer "Mozart"`) en un
fichero YAML con TODAS las representaciones recibidas, de modo que el
desarrollo de la fusión se hace sobre ese fichero y NUNCA se vuelve a consultar
Internet.

Uso (una sola vez por consulta):
    python tests/fusion/capture.py --composer Mozart
    python tests/fusion/capture.py --title "Ave Verum Corpus"

Guarda por defecto en tests/golden/<slug>_<fecha>.yaml.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

import yaml

from src.osap.bootstrap.configuration import load_configuration
from src.osap.bootstrap.container import Container
from src.osap.bootstrap.wiring import wire
from src.osap.domain.resolve_request import ResolveRequest

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"


def _slug(text: str | None) -> str:
    if not text:
        return "consulta"
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def main() -> int:
    parser = argparse.ArgumentParser(description="Captura una consulta de OSAP como golden dataset.")
    parser.add_argument("--composer", help="Compositor a buscar.")
    parser.add_argument("--title", help="Título a buscar.")
    parser.add_argument("--query", help="Consulta libre.")
    parser.add_argument("--out", type=Path, help="Ruta de salida (por defecto tests/golden/...).")
    args = parser.parse_args()

    if not (args.composer or args.title or args.query):
        print("Indica --composer, --title o --query.")
        return 2

    request = ResolveRequest(composer=args.composer, title=args.title, query=args.query)
    container = wire(Container(), load_configuration())
    engine = container.work_resolution_engine()
    print(f"Consultando: {request.composer or request.title or request.query}")
    ranked = engine.rank(request)
    reps = [
        {
            "title": c.work_descriptor.title,
            "composer": c.work_descriptor.composer,
            "provider": c.provider_id.value,
            "format": c.format.value,
            "downloadable": c.downloadable,
            "manual_download": c.manual_download,
            "download_url": c.download_url,
            "license": c.license,
        }
        for c in ranked
    ]
    if not reps:
        print("Sin representaciones.")
        return 1

    slug = _slug(args.composer or args.title or args.query)
    date = datetime.date.today().isoformat()
    out = args.out or (GOLDEN_DIR / f"{slug}_{date}.yaml")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(reps, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"{len(reps)} representaciones guardadas en: {out}")
    print("Ya no vuelvas a consultar Internet para esta búsqueda; desarrolla sobre este fichero:")
    print(f'  python tests/fusion/fusion_test.py "{out}" --group')
    return 0


if __name__ == "__main__":
    sys.exit(main())
