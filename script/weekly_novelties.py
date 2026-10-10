#!/usr/bin/env python
"""Rutina semanal de novedades y normalización: import → normalize → index → IndexNow.

Fases (seleccionables con `--phases`, por defecto todas):

  1. **import** — metadatos de IMSLP (`import_imslp_works`) y, si se pasa `--cpdl-dir`,
     el export de CPDL (`import_cpdl_works`, con guarda `--cpdl-min-files`).
  2. **normalize** — pipeline de normalización/identidad en osap-storage: entidades HTML,
     ensembles, idiomas, géneros/instrumentación y **resolución de personas**
     (`parse_import_persons` → `resolve_persons` → `link_*` → `populate_persons_from_import`
     → limpieza/canonización de nombres → `merge_duplicate_persons` → `mark_pseudo_persons`).
  3. **index** — `rebuild_index.py` (sin IndexNow) → `resolve_index_composers` →
     `finalize_index_identity` → **IndexNow** (ya con identidad coherente).

Cada paso corre en su directorio/venv (osap-storage para imports/normalización; osap-api para
el índice). Es best-effort: un paso que falla se registra y se continúa.

`--apply` controla **toda** la escritura; sin él (dry-run) los pasos se lanzan en modo
validación (IMSLP sin escribir, CPDL con `--dry-run`, normalize con `--dry-run`, index sin
`--apply`, IndexNow omitido).

Uso (desde osap-api):
    python script/weekly_novelties.py --apply
    python script/weekly_novelties.py --apply --cpdl-dir /home/ocw/imports/cpdl
    python script/weekly_novelties.py --apply --phases normalize,index   # solo reconciliar
    python script/weekly_novelties.py --phases normalize,index           # dry-run
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORAGE_DIR = "/home/ocw/openmusicrepository.com/osap-storage"

_ALL_PHASES = ("import", "normalize", "index")


def _storage_python(storage_dir: str) -> str:
    """Python del venv de osap-storage (POSIX o Windows)."""
    base = Path(storage_dir) / ".venv"
    win = base / "Scripts" / "python.exe"
    return str(win if win.exists() else base / "bin" / "python")


def _cpdl_export_ok(cpdl_dir: str | None, min_files: int) -> bool:
    """True si el export de CPDL tiene al menos `min_files` ficheros `.xml`.

    Salvaguarda: `import_cpdl_works` hace `DELETE FROM works WHERE works_origin='CPDL'` antes
    de reinsertar, así que un export vacío/parcial borraría el corpus. Se exige un mínimo.
    """
    if not cpdl_dir:
        return False
    return sum(1 for _ in Path(cpdl_dir).glob("*.xml")) >= max(1, min_files)


def _import_steps(args: argparse.Namespace, py: str) -> list[tuple[str, str, list[str]]]:
    sd = args.storage_dir
    apply_flag = ["--apply"] if args.apply else []
    steps: list[tuple[str, str, list[str]]] = []
    if not args.skip_imslp:
        steps.append(("imslp", sd,
                      [py, "-m", "scripts.import_imslp_works", "--db", args.storage_db, *apply_flag]))
    if args.cpdl_dir:
        steps.append(("cpdl", sd,
                      [py, "-m", "scripts.import_cpdl_works", "--db", args.storage_db,
                       "--dir", args.cpdl_dir, *( [] if args.apply else ["--dry-run"])]))
    return steps


def _normalize_steps(args: argparse.Namespace, py: str) -> list[tuple[str, str, list[str]]]:
    """Pipeline de normalización/identidad en osap-storage (orden importa)."""
    sd, db = args.storage_dir, args.storage_db
    dry = [] if args.apply else ["--dry-run"]   # scripts que aplican por defecto
    app = ["--apply"] if args.apply else []      # scripts que aplican solo con --apply

    def s(name: str, *extra: str) -> tuple[str, str, list[str]]:
        return ("normalize", sd, [py, "-m", f"scripts.{name}", *extra])

    steps = [
        s("fix_html_entities", *app),
        s("normalize_ensembles", *dry),
        s("populate_ensemble_voices", *dry),
        s("fill_language_names", *dry),
    ]
    if args.cpdl_dir:
        steps.append(s("map_cpdl_genres", "--dir", args.cpdl_dir, "--db", db, *dry))
    steps += [
        s("parse_import_persons", *app),
        s("resolve_persons", "--db", db, *dry),
        s("link_works_person_import", "--db", db, *dry),
        s("link_import_by_identity", "--db", db, *dry),
        s("populate_persons_from_import", "--db", db, "--roles", "composer", *dry),
        s("clean_person_names_chars", *app),
        s("normalize_identity_names", "--db", db, *dry),
        s("clean_persons", *app),
        s("merge_duplicate_persons", "--db", db, *dry),
        s("mark_pseudo_persons", *app),
    ]
    return steps


def _index_steps(args: argparse.Namespace) -> list[tuple[str, str, list[str]]]:
    """Reindexado + identidad del índice + IndexNow (osap-api)."""
    root = str(ROOT)
    apply_flag = ["--apply"] if args.apply else []
    id_args = ["--db-host", args.db_host, "--db-user", args.db_user,
               "--db-password", args.db_password, "--db-omr", args.db_omr, "--db-api", args.db_api]
    steps: list[tuple[str, str, list[str]]] = []
    if args.apply and not args.skip_reindex:
        steps.append(("reindex", root,
                      [sys.executable, str(ROOT / "script" / "rebuild_index.py"),
                       "--providers", args.providers,
                       "--host", args.db_host, "--user", args.db_user,
                       "--password", args.db_password, "--database", args.db_api,
                       "--db-api", args.db_api, "--db-omr", args.db_omr]))
    steps.append(("index-identity", root,
                  [sys.executable, str(ROOT / "script" / "finalize_index_identity.py"),
                   *apply_flag, *id_args]))
    if args.apply:
        steps.append(("indexnow", root,
                      [sys.executable, str(ROOT / "script" / "indexnow.py"),
                       "--days", str(args.days), "--host", args.db_host, "--user", args.db_user,
                       "--password", args.db_password, "--database", args.db_api]))
    return steps


def _steps(args: argparse.Namespace) -> list[tuple[str, str, list[str]]]:
    """Pasos a ejecutar como `(kind, cwd, cmd)`, en orden. Función pura (testeable)."""
    py = _storage_python(args.storage_dir)
    phases = set(args.phases.split(","))
    steps: list[tuple[str, str, list[str]]] = []
    if "import" in phases:
        steps += _import_steps(args, py)
    if "normalize" in phases:
        steps += _normalize_steps(args, py)
    if "index" in phases:
        steps += _index_steps(args)
    return steps


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="escribe (import/normalize/index) y reindexa; sin él, dry-run")
    ap.add_argument("--phases", default=",".join(_ALL_PHASES),
                    help=f"fases a ejecutar: {','.join(_ALL_PHASES)}")
    ap.add_argument("--providers", default="imslp,cpdl", help="proveedores a reindexar")
    ap.add_argument("--days", type=int, default=7, help="ventana de IndexNow (días)")
    ap.add_argument("--cpdl-dir", default=None, help="export MediaWiki de CPDL (opcional)")
    ap.add_argument("--cpdl-min-files", type=int, default=1,
                    help="mínimo de .xml exigidos en el export de CPDL (0 se eleva a 1)")
    ap.add_argument("--skip-imslp", action="store_true", help="no materializar IMSLP")
    ap.add_argument("--skip-reindex", action="store_true", help="no reindexar (solo identidad)")
    ap.add_argument("--storage-dir", default=DEFAULT_STORAGE_DIR)
    ap.add_argument("--storage-db", default="osap_storage")
    ap.add_argument("--db-host", default=os.environ.get("OSAP_INDEX_DB_HOST", "127.0.0.1"))
    ap.add_argument("--db-user", default=os.environ.get("OSAP_INDEX_DB_USER", "osap2027"))
    ap.add_argument("--db-password", default=os.environ.get("OSAP_INDEX_DB_PASSWORD", "2027osapdb"))
    ap.add_argument("--db-api", default=os.environ.get("OSAP_INDEX_DB_API", "osap-api"))
    ap.add_argument("--db-omr", default=os.environ.get("OSAP_INDEX_DB_OMR", "osap-storage"))
    args = ap.parse_args()

    failures = 0
    for kind, cwd, cmd in _steps(args):
        if kind == "cpdl" and not _cpdl_export_ok(args.cpdl_dir, args.cpdl_min_files):
            print(f"CPDL: export insuficiente en {args.cpdl_dir} "
                  f"(< {max(1, args.cpdl_min_files)} .xml); se omite el import", flush=True)
            failures += 1
            continue
        print("+ " + " ".join(cmd), flush=True)
        try:
            rc = subprocess.call(cmd, cwd=cwd, env={**os.environ, "PYTHONPATH": cwd})
        except OSError as exc:
            print(f"  error al lanzar el paso: {exc}", flush=True)
            rc = 1
        if rc != 0:
            failures += 1
            print(f"  paso falló (código {rc}); se continúa (best-effort)", flush=True)
    print(f"rutina semanal terminada; pasos con error: {failures}")
    return 0  # best-effort: el timer no debe marcarse en fallo por un paso opcional


if __name__ == "__main__":
    raise SystemExit(main())
