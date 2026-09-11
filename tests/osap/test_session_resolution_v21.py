"""F3.5 — integración del puente V2.1 en sesiones (AcquisitionService).

El flujo real de una sesión usa `SessionUniverseResolver` (V2.1 + ResolutionDecisionPolicy
+ serialización canónica). Se verifican: provisional/definitivo, paridad de estados con el
`SimpleUniverseMatcher` anterior y estabilidad de revisión (mismo universo → sin bump).
"""

import json
from datetime import UTC, datetime, timedelta

from src.osap.infrastructure.resolution.acquisition_service import AcquisitionService
from src.osap.infrastructure.resolution.domain_adapter import provider_works_to_candidates
from src.osap.infrastructure.resolution.provider_acquirer import FakePaginatedAcquirer
from src.osap.infrastructure.resolution.session_universe_resolver import SessionUniverseResolver
from src.osap.infrastructure.resolution.universe_matching import SimpleUniverseMatcher
from src.osap.infrastructure.state.resolution_store import _MemoryStore


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _make_session(
    store: _MemoryStore,
    providers: list[str],
    policy: dict[str, object] | None = None,
) -> str:
    session_id = "ses_v21"
    store.create_session(
        session_id,
        json.dumps({"query": "Mozart", "works": []}),
        json.dumps(providers),
        json.dumps(policy or {}),
        _now(),
        (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
    )
    return session_id


def test_session_flow_uses_v21_and_ends_complete() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=2, per_page=2)
    service = AcquisitionService(store, {"fake": fake}, SessionUniverseResolver())

    assert service.run_until_terminal(session_id) == "complete"
    rows, total = store.list_results(session_id, 0, 100)
    assert total == 4
    assert all(r["resolution_stage"] == "definitive" for r in rows)
    assert all(r["status"] in ("resolved", "ambiguous", "not_found") for r in rows)


def test_provisional_then_definitive_stages() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=2, per_page=2)
    service = AcquisitionService(store, {"fake": fake}, SessionUniverseResolver())

    service.process_step(session_id)
    rows1, _ = store.list_results(session_id, 0, 100)
    assert rows1 and all(r["resolution_stage"] == "provisional" for r in rows1)

    service.run_until_terminal(session_id)
    rows2, _ = store.list_results(session_id, 0, 100)
    assert rows2 and all(r["resolution_stage"] == "definitive" for r in rows2)


def test_recompute_same_universe_does_not_bump_revision() -> None:
    store = _MemoryStore()
    session_id = _make_session(store, ["fake"])
    fake = FakePaginatedAcquirer(total_pages=1, per_page=3)
    service = AcquisitionService(store, {"fake": fake}, SessionUniverseResolver())
    service.run_until_terminal(session_id)

    rows, _ = store.list_results(session_id, 0, 100)
    assert rows
    revisions_before = [int(r["revision"]) for r in rows]

    changed = service.recompute_items(session_id, "definitive")
    assert changed == 0
    rows2, _ = store.list_results(session_id, 0, 100)
    assert [int(r["revision"]) for r in rows2] == revisions_before


def _status_by_title(rows: list[dict[str, object]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        normalized = json.loads(str(row.get("normalized_json") or "{}"))
        title = str(normalized.get("title") or "?")
        out[title] = str(row.get("status"))
    return out


def test_status_parity_with_simple_universe_matcher() -> None:
    # Dos proveedores con el mismo corpus -> coincidencias reales (resolved) y obras sueltas.
    def _run(matcher: object) -> dict[str, str]:
        store = _MemoryStore()
        session_id = _make_session(store, ["fake1", "fake2"])
        acquirers = {
            "fake1": FakePaginatedAcquirer(total_pages=1, per_page=3, title_prefix="Fake Work"),
            "fake2": FakePaginatedAcquirer(total_pages=1, per_page=3, title_prefix="Fake Work"),
        }
        service = AcquisitionService(store, acquirers, matcher)  # type: ignore[arg-type]
        service.run_until_terminal(session_id)
        rows, _ = store.list_results(session_id, 0, 100)
        return _status_by_title(rows)

    new = _run(SessionUniverseResolver())
    legacy = _run(SimpleUniverseMatcher())
    assert sorted(new) == sorted(legacy)
    assert all(new[title] == legacy[title] for title in new)


def test_typed_candidates_path_produces_items() -> None:
    fake = FakePaginatedAcquirer(total_pages=1, per_page=2)
    page = fake.acquire_page("fake", "1", "Mozart")
    candidates = provider_works_to_candidates("fake", page.works)
    items = SessionUniverseResolver().resolve_candidates(candidates)
    assert len(items) == 2
    assert all(item["status"] in ("resolved", "ambiguous", "not_found") for item in items)
    assert len({item["id"] for item in items}) == 2
