"""Tests funcionales del circuito de SELECCIÓN entre representaciones YA conocidas.

El circuito NO crea sesión, NO adquiere y NO consulta proveedores: selecciona entre
la lista conocida (la que alimenta la UI), persiste POR WORK y lo re-expone.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

import src.osap.api.platform as platform_module
from src.osap.api.contracts import RepresentationInput
from src.osap.infrastructure.state.op_store import _MemoryStore

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "musicxml"
REAL_MXL = (FIXTURES / "real_short.mxl").read_bytes()


def _api(monkeypatch: pytest.MonkeyPatch) -> Any:
    """API sin container ni acquisition: si intentara proveedores/sesión fallaría."""
    api: Any = platform_module.PlatformApi.__new__(platform_module.PlatformApi)
    api._store = _MemoryStore()
    api._resolution_store = None
    from src.osap.application import representation_selector

    def fake_download(url: str) -> bytes | None:
        return REAL_MXL if "omr" in url else None

    monkeypatch.setattr(representation_selector, "_download", fake_download)
    return api


def _rep(provider: str, fmt: str = "musicxml", url: str | None = None, rid: str | None = None) -> RepresentationInput:
    return RepresentationInput(
        id=rid or f"{provider}-{fmt}-1",
        provider=provider,
        format=fmt,
        url=url or f"https://storage.openmusicrepository.com/api/download/{provider}.mxl",
    )


class TestSelectBest:
    def test_a_una_musicxml_conocida_se_selecciona(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _api(monkeypatch)
        result = api.select_best_representation("work-1", [_rep("omr")])
        assert result.representations_known == 1
        assert result.candidates_usable == 1
        assert result.status == "selected"
        assert result.selected is not None
        assert result.selected["provider"] == "omr"
        assert result.selected["format"] == "musicxml"

    def test_b_varias_conocidas_recibe_exactamente_esas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _api(monkeypatch)
        reps = [_rep("omr"), _rep("imslp"), _rep("cpdl", url="https://www.cpdl.org/wiki/x") ]
        result = api.select_best_representation("work-1", reps)
        assert result.representations_known == 3
        assert result.candidates_usable == 3
        assert result.status == "selected"

    def test_c_cero_representaciones_conocidas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _api(monkeypatch)
        result = api.select_best_representation("work-1", [])
        assert result.representations_known == 0
        assert result.candidates_usable == 0
        assert result.status == "none_known"
        assert result.selected is None
        assert "No hay representaciones conocidas" in result.message

    def test_d_conocidas_pero_ninguna_utilizable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _api(monkeypatch)
        result = api.select_best_representation(
            "work-1",
            [_rep("cpdl", url="https://www.cpdl.org/wiki/page", fmt="pdf")],
        )
        # URL http existe pero el contenido no valida (download devuelve None para no-omr)
        assert result.representations_known == 1
        assert result.status == "none_usable"
        assert result.selected is None

    def test_e_repeticion_idempotente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _api(monkeypatch)
        first = api.select_best_representation("work-1", [_rep("omr")])
        second = api.select_best_representation("work-1", [_rep("omr")])
        assert first.selected == second.selected
        # Sin sesiones ni duplicados: solo una fila de selección por work.
        store = api._store
        row = store.get_work_selection("work-1")
        assert row is not None
        assert store.get_work_selection("work-otra") is None

    def test_f_persistencia_por_work(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _api(monkeypatch)
        api.select_best_representation("work-42", [_rep("omr")])
        reloaded = api.get_work_selection("work-42")
        assert reloaded is not None
        assert reloaded.status == "selected"
        assert reloaded.selected is not None and reloaded.selected["provider"] == "omr"
        assert api.get_work_selection("otra") is None

    def test_g_sin_discovery_ni_adquisicion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # El api se construyó sin container, sin resolution_store y sin acquisition:
        # ejecutar la selección solo es posible si NO toca proveedores ni sesiones.
        api = _api(monkeypatch)
        result = api.select_best_representation("work-1", [_rep("omr")])
        assert result.status == "selected"
