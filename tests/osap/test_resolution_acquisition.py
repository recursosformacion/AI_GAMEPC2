"""FASE 2 — máquina de adquisición idempotente y reanudable.

Prueba las garantías sobre un proveedor paginado determinista (fake): una página se guarda
una sola vez, reiniciar el worker no pierde el cursor, la sesión continúa, el progreso se
refleja, los resultados siguen vacíos (sin matching), y los límites producen `partial` en
vez de inventar `complete`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from src.osap.infrastructure.resolution.acquisition_service import AcquisitionService
from src.osap.infrastructure.resolution.provider_acquirer import FakePaginatedAcquirer
from src.osap.infrastructure.state.resolution_store import _MemoryStore


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _future() -> str:
    return (datetime.now(UTC) + timedelta(minutes=30)).isoformat()


def _make_session(
    store: _MemoryStore,
    providers: list[str],
    policy: dict[str, object] | None = None,
) -> str:
    session_id = "ses_test"
    store.create_session(
        session_id,
        json.dumps({"query": "Mozart", "works": []}),
        json.dumps(providers),
        json.dumps(policy or {}),
        _now(),
        _future(),
    )
    return session_id


def _service(store: _MemoryStore, fake: FakePaginatedAcquirer) -> AcquisitionService:
    return AcquisitionService(store, {"fake": fake})


def test_single_fetch_is_stored_once_and_completes() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=1, per_page=5)
    service = _service(store, fake)

    assert service.process_step(session_id) == "complete"
    rows = store.list_provider_results(session_id, "fake")
    assert len(rows) == 1
    assert rows[0]["status"] == "end_of_provider"

    # Ya completa: repetir el paso no duplica ni cambia nada.
    assert service.process_step(session_id) == "complete"
    assert len(store.list_provider_results(session_id, "fake")) == 1


def test_multi_page_eof_complete() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=3, per_page=5)
    service = _service(store, fake)

    assert service.run_until_terminal(session_id) == "complete"
    rows = store.list_provider_results(session_id, "fake")
    assert len(rows) == 3
    assert [r["next_cursor"] for r in rows] == ["2", "3", None]
    assert rows[-1]["status"] == "end_of_provider"


def test_page_not_duplicated_on_retry() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=2, per_page=5)
    service = _service(store, fake)

    service.process_step(session_id)  # página 1
    before = len(store.list_provider_results(session_id, "fake"))
    assert before == 1

    # Reintento de la misma página (misma clave) tras un "crash" antes de avanzar.
    store.add_provider_result(
        "pr_dup",
        session_id,
        "fake",
        "cursor",
        "1",
        "2",
        "fetched",
        "[]",
        "{}",
        _now(),
    )
    assert len(store.list_provider_results(session_id, "fake")) == 1


def test_restart_worker_continues_from_next_cursor() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=3, per_page=5)
    first = _service(store, fake)
    first.process_step(session_id)  # solo página 1

    # "Reinicio": nueva instancia del worker, mismo store (OpStore persiste).
    restarted = AcquisitionService(store, {"fake": FakePaginatedAcquirer(total_pages=3, per_page=5)})
    assert restarted.next_session_id() == session_id
    assert restarted.run_until_terminal(session_id) == "complete"

    rows = store.list_provider_results(session_id, "fake")
    assert len(rows) == 3
    # No se re-consultó la página 1 (se retomó desde el next_cursor persistido).
    assert rows[0]["cursor_value"] == "1"
    assert rows[1]["cursor_value"] == "2"
    assert rows[2]["cursor_value"] == "3"


def test_limit_max_pages_produces_partial() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"], {"max_pages_per_provider": 3})
    fake = FakePaginatedAcquirer(total_pages=10, per_page=5)
    service = _service(store, fake)

    assert service.run_until_terminal(session_id) == "partial"
    assert len(store.list_provider_results(session_id, "fake")) == 3


def test_limit_max_results_produces_partial() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"], {"max_results_to_acquire": 12})
    fake = FakePaginatedAcquirer(total_pages=10, per_page=5)
    service = _service(store, fake)

    assert service.run_until_terminal(session_id) == "partial"
    # 5 + 5 + 5 = 15 >= 12 -> se para tras 3 páginas (partial), sin llegar a EOF.
    assert len(store.list_provider_results(session_id, "fake")) == 3


def test_progress_reflected_and_results_empty() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=2, per_page=5)
    service = _service(store, fake)
    service.run_until_terminal(session_id)

    session = store.get_session(session_id)
    progress = json.loads(str(session["progress_json"]))
    assert progress["acquired_pages"] == 2
    assert progress["acquired_works"] == 10
    assert progress["providers"]["fake"]["pages"] == 2
    assert progress["providers"]["fake"]["works"] == 10
    assert session["status"] == "complete"

    # Sin matching todavía: los resultados siguen vacíos.
    rows, total = store.list_results(session_id, 0, 25)
    assert total == 0
    assert rows == []


def test_recoverable_error_does_not_invent_complete() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=3, per_page=5, fail_pages={2})
    service = _service(store, fake)

    status = service.run_until_terminal(session_id)
    # La página 2 falla de forma recuperable: no inventamos complete.
    assert status == "acquiring" or status == "partial"
    rows = store.list_provider_results(session_id, "fake")
    assert any(r["status"] == "recoverable_error" for r in rows)
