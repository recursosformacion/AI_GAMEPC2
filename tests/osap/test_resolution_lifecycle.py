"""FASE 4 — resolución definitiva y cierre de sesión.

Cubre: matching definitivo (`resolution_stage=definitive`) al terminar; `complete` vs
`partial` estrictos (errores recuperables → `partial`); TTL (`expired` + limpieza de
datos); y la explicabilidad de cada candidato (scoring desglosado).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from src.osap.infrastructure.resolution.acquisition_service import AcquisitionService
from src.osap.infrastructure.resolution.provider_acquirer import FakePaginatedAcquirer
from src.osap.infrastructure.resolution.universe_matching import SimpleUniverseMatcher
from src.osap.infrastructure.state.resolution_store import _MemoryStore

_SCORE_KEYS = {"matching_providers", "title_score", "catalogue_score", "composer_score", "final_score"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _future(minutes: int = 30) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


def _make_session(
    store: _MemoryStore,
    providers: list[str],
    policy: dict[str, object] | None = None,
    expires: str | None = None,
) -> str:
    session_id = "ses_life"
    store.create_session(
        session_id,
        json.dumps({"query": "Mozart", "works": []}),
        json.dumps(providers),
        json.dumps(policy or {}),
        _now(),
        expires or _future(),
    )
    return session_id


def test_definitive_matching_on_complete() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=2, per_page=2)
    service = AcquisitionService(store, {"fake": fake}, SimpleUniverseMatcher())

    status = service.run_until_terminal(session_id)
    assert status == "complete"
    session = store.get_session(session_id)
    assert session["status"] == "complete"

    rows, total = store.list_results(session_id, 0, 100)
    assert total == 4
    assert all(r["resolution_stage"] == "definitive" for r in rows)


def test_partial_when_recoverable_error_never_resolved() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=2, per_page=2, fail_pages={1})
    service = AcquisitionService(store, {"fake": fake}, SimpleUniverseMatcher())

    status = service.run_until_terminal(session_id)
    # Nunca se llega a EOF: error recuperable pendiente -> partial, nunca complete.
    assert status == "partial"
    assert store.get_session(session_id)["status"] == "partial"


def test_complete_strictly_requires_eof_no_pending() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"], {"max_pages_per_provider": 3})
    fake = FakePaginatedAcquirer(total_pages=10, per_page=2)
    service = AcquisitionService(store, {"fake": fake}, SimpleUniverseMatcher())

    status = service.run_until_terminal(session_id)
    # Límite alcanzado sin EOF -> partial (no se inventa complete).
    assert status == "partial"


def test_ttl_expires_and_cleans_child_data() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"], expires=_future(minutes=-5))  # ya caducada
    fake = FakePaginatedAcquirer(total_pages=2, per_page=2)
    service = AcquisitionService(store, {"fake": fake}, SimpleUniverseMatcher())

    status = service.process_step(session_id)
    assert status == "expired"
    assert store.get_session(session_id)["status"] == "expired"
    # Datos hijos eliminados; la sesión se conserva como `expired` (no catálogo).
    assert store.list_all_provider_results(session_id) == []
    assert store.list_results(session_id, 0, 100)[1] == 0


def test_candidates_carry_explainable_scoring() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=1, per_page=2)
    service = AcquisitionService(store, {"fake": fake}, SimpleUniverseMatcher())
    service.run_until_terminal(session_id)

    rows, _ = store.list_results(session_id, 0, 100)
    assert rows
    candidates = json.loads(str(rows[0]["candidates_json"]))
    assert candidates
    assert set(candidates[0]) >= _SCORE_KEYS


def test_provisional_during_acquisition_then_definitive() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=2, per_page=2)
    service = AcquisitionService(store, {"fake": fake}, SimpleUniverseMatcher())

    service.process_step(session_id)  # aún adquiriendo
    rows1, _ = store.list_results(session_id, 0, 100)
    assert rows1 and all(r["resolution_stage"] == "provisional" for r in rows1)

    service.run_until_terminal(session_id)
    rows2, _ = store.list_results(session_id, 0, 100)
    assert rows2 and all(r["resolution_stage"] == "definitive" for r in rows2)
