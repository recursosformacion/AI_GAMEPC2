"""Tests de la rutina semanal de novedades (composición de pasos, sin ejecutar)."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

_SPEC = importlib.util.spec_from_file_location(
    "weekly_novelties", Path(__file__).resolve().parents[2] / "script" / "weekly_novelties.py"
)
assert _SPEC is not None and _SPEC.loader is not None
weekly: ModuleType = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(weekly)


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "apply": True,
        "phases": "import,normalize,index",
        "providers": "imslp,cpdl",
        "days": 7,
        "cpdl_dir": None,
        "cpdl_min_files": 1,
        "skip_imslp": False,
        "skip_reindex": False,
        "storage_dir": "/x/osap-storage",
        "storage_db": "osap_storage",
        "db_host": "127.0.0.1",
        "db_user": "u",
        "db_password": "p",
        "db_api": "osap_api",
        "db_omr": "osap_storage",
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _kinds(steps: list[tuple[str, str, list[str]]]) -> list[str]:
    return [kind for kind, _cwd, _cmd in steps]


def test_apply_encadena_import_normalize_index_e_indexnow() -> None:
    steps = weekly._steps(_args())
    kinds = _kinds(steps)
    assert {"imslp", "normalize", "reindex", "index-identity", "indexnow"} <= set(kinds)
    indexnow = next(cmd for kind, _cwd, cmd in steps if kind == "indexnow")
    assert "indexnow.py" in indexnow[1]
    reindex = next(cmd for kind, _cwd, cmd in steps if kind == "reindex")
    assert "--indexnow" not in reindex  # IndexNow es un paso aparte, al final


def test_pasos_de_storage_usan_su_propio_cwd() -> None:
    steps = weekly._steps(_args())
    for kind, cwd, cmd in steps:
        if kind in {"imslp", "cpdl", "normalize"}:
            assert cwd == "/x/osap-storage"
            assert cmd[1] == "-m" and cmd[2].startswith("scripts.")


def test_normalize_incluye_resolucion_de_personas() -> None:
    cmds = " ".join(" ".join(cmd) for kind, _cwd, cmd in weekly._steps(_args()) if kind == "normalize")
    for script in ("resolve_persons", "populate_persons_from_import", "merge_duplicate_persons"):
        assert f"scripts.{script}" in cmds


def test_cpdl_solo_si_hay_export() -> None:
    assert "cpdl" not in _kinds(weekly._steps(_args()))
    con = weekly._steps(_args(cpdl_dir="/imports/cpdl"))
    cpdl = next(cmd for kind, _cwd, cmd in con if kind == "cpdl")
    assert "/imports/cpdl" in cpdl


def test_dry_run_no_escribe_y_omite_reindex_e_indexnow() -> None:
    steps = weekly._steps(_args(apply=False))
    kinds = _kinds(steps)
    assert "reindex" not in kinds and "indexnow" not in kinds
    imslp = next(cmd for kind, _cwd, cmd in steps if kind == "imslp")
    assert "--apply" not in imslp
    resolve = next(cmd for kind, _cwd, cmd in steps if kind == "normalize" and "scripts.resolve_persons" in cmd)
    assert "--dry-run" in resolve  # normalize propaga el dry-run
    cpdl_steps = weekly._steps(_args(apply=False, cpdl_dir="/imports/cpdl"))
    cpdl = next(cmd for kind, _cwd, cmd in cpdl_steps if kind == "cpdl")
    assert "--dry-run" in cpdl


def test_fases_seleccionables() -> None:
    kinds = _kinds(weekly._steps(_args(phases="normalize,index")))
    assert "imslp" not in kinds and "normalize" in kinds


def test_skip_imslp_y_skip_reindex() -> None:
    kinds = _kinds(weekly._steps(_args(skip_imslp=True, skip_reindex=True)))
    assert "imslp" not in kinds and "reindex" not in kinds


def test_cpdl_export_ok_exige_un_minimo_de_xml(tmp_path: Path) -> None:
    d = tmp_path / "cpdl"
    d.mkdir()
    assert weekly._cpdl_export_ok(str(d), 1) is False
    (d / "a.xml").write_text("<x/>", encoding="utf-8")
    assert weekly._cpdl_export_ok(str(d), 1) is True
    assert weekly._cpdl_export_ok(str(d), 2) is False
    assert weekly._cpdl_export_ok(None, 1) is False
