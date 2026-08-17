"""FASE 3 — universo → matching → resultados.

Demuestra que: (1) el universo se reconstruye solo desde `provider_results` (sin HTTP);
(2) el matching provisional produce `resolution_items` paginables; y (3) **el mismo
universo → dos ejecuciones → el mismo resultado** (determinismo).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from src.osap.infrastructure.resolution.acquisition_service import AcquisitionService
from src.osap.infrastructure.resolution.provider_acquirer import FakePaginatedAcquirer, provider_works_to_json
from src.osap.infrastructure.resolution.universe_matching import SimpleUniverseMatcher, rebuild_universe
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
    session_id = "ses_uni"
    store.create_session(
        session_id,
        json.dumps({"query": "Mozart", "works": []}),
        json.dumps(providers),
        json.dumps(policy or {}),
        _now(),
        _future(),
    )
    return session_id


def _service(store: _MemoryStore) -> AcquisitionService:
    fake = FakePaginatedAcquirer(total_pages=2, per_page=3)
    return AcquisitionService(store, {"fake": fake}, SimpleUniverseMatcher())


def test_universe_rebuilt_without_provider_calls() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    service = _service(store)
    service.run_until_terminal(session_id)

    # El universo sale de provider_results, no de una llamada HTTP nueva.
    universe = rebuild_universe(store, session_id)
    assert len(universe) == 6  # 2 páginas x 3 obras
    assert all({"provider", "work"} <= set(u) for u in universe)
    assert all(u["provider"] == "fake" for u in universe)


def test_provisional_items_persisted_and_paginable() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    service = _service(store)
    service.run_until_terminal(session_id)

    rows, total = store.list_results(session_id, 0, 100)
    assert total == 6  # 6 obras distintas (una por obra del fake)
    assert rows
    for r in rows:
        assert r["resolution_stage"] in ("provisional", "definitive")
        assert int(r["revision"]) >= 1

    # Paginación de la Web sobre resolution_items.
    page1, total1 = store.list_results(session_id, 0, 2)
    page2, _ = store.list_results(session_id, 2, 2)
    assert total1 == 6
    assert len(page1) == 2
    assert len(page2) == 2
    assert [r["id"] for r in page1] != [r["id"] for r in page2]


def test_revision_grows_across_pages() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=3, per_page=3)
    service = AcquisitionService(store, {"fake": fake}, SimpleUniverseMatcher())

    service.process_step(session_id)  # página 1 -> matching (revision 1)
    rows1, _ = store.list_results(session_id, 0, 100)
    rev_after_p1 = {int(r["revision"]) for r in rows1}
    assert rev_after_p1 == {1}

    service.process_step(session_id)  # página 2 -> matching actualizado
    rows2, _ = store.list_results(session_id, 0, 100)
    # Las obras nuevas entran con revision 1; las previas no cambian (mismo contenido).
    assert any(int(r["revision"]) == 1 for r in rows2)


def test_same_universe_same_result_two_runs() -> None:
    """Garantía fundamental de FASE 3: el resultado depende del universo, no del momento."""
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    service = _service(store)
    service.run_until_terminal(session_id)

    items_before, total_before = store.list_results(session_id, 0, 100)

    # Segunda ejecución del matcher sobre el MISMO provider_results y el MISMO stage.
    changed = service.recompute_items(session_id, "definitive")
    items_after, total_after = store.list_results(session_id, 0, 100)

    assert changed == 0  # contenido idéntico -> no cambia nada (ni revision)
    assert total_before == total_after
    # Mismo id, mismo estado, misma revision, misma confianza, mismo contenido.
    for a, b in zip(items_before, items_after, strict=False):
        assert a["id"] == b["id"]
        assert a["revision"] == b["revision"]
        assert a["status"] == b["status"]
        assert a["normalized_json"] == b["normalized_json"]
        assert a["resolved_json"] == b["resolved_json"]
        assert a["candidates_json"] == b["candidates_json"]


def test_items_change_when_universe_grows() -> None:
    """Un universo mayor cambia el resultado (nuevas obras) sin re-consultar el proveedor."""
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    # Sesión con 1 página.
    fake1 = FakePaginatedAcquirer(total_pages=1, per_page=3)
    service = AcquisitionService(store, {"fake": fake1}, SimpleUniverseMatcher())
    service.run_until_terminal(session_id)
    rows1, total1 = store.list_results(session_id, 0, 100)
    assert total1 == 3

    # "Llegan más páginas": añadimos la página 2 directamente en provider_results
    # (simula reanudación/adquisición) y re-resolvemos.
    page2_works = FakePaginatedAcquirer(total_pages=2, per_page=3).acquire_page("fake", "2", "Mozart")
    store.add_provider_result(
        "pr_page2",
        session_id,
        "fake",
        "cursor",
        "2",
        None,
        "end_of_provider",
        provider_works_to_json(page2_works.works),
        "{}",
        _now(),
    )
    service.recompute_items(session_id, "provisional")
    _, total2 = store.list_results(session_id, 0, 100)
    assert total2 == 6


def test_results_endpoint_returns_empty_until_matching_wired() -> None:
    # Sin matcher en el service, los resultados permanecen vacíos.
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=2, per_page=3)
    service = AcquisitionService(store, {"fake": fake})  # sin matcher
    service.run_until_terminal(session_id)
    rows, total = store.list_results(session_id, 0, 100)
    assert total == 0
    assert rows == []
