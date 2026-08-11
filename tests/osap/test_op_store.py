import pytest

from src.osap.infrastructure.state.op_store import OpStore


@pytest.fixture()
def store(tmp_path):
    return OpStore(str(tmp_path / "op.db"))


def test_suggestion_roundtrip(store: OpStore) -> None:
    added = store.add_suggestion(
        "sug-1", "CPDL2", "HTTP", "https://x", {"title": "title"}, "user-1"
    )
    assert added["status"] == "pending"
    assert store.pending_suggestion_count() == 1

    resolved = store.resolve_suggestion("sug-1", "approved", "ok", "admin-1")
    assert resolved is not None
    assert resolved["status"] == "approved"
    assert resolved["decided_by"] == "admin-1"
    assert store.pending_suggestion_count() == 0


def test_provider_upsert_and_wired(store: OpStore) -> None:
    store.upsert_provider("prov-x", "Provider X", base_url="https://x", wired=False, config={"k": "v"})
    assert store.get_provider("prov-x")["wired"] == 0
    store.set_provider_wired("prov-x", True)
    assert store.get_provider("prov-x")["wired"] == 1


def test_app_config(store: OpStore) -> None:
    assert store.get_config("missing") is None
    store.set_config("theme", "dark")
    assert store.get_config("theme") == "dark"
    store.set_config("theme", "light")
    assert store.get_config("theme") == "light"
