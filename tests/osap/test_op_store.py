import pytest

from src.osap.infrastructure.state.op_store import OpStore

TEST_DB = "osap_api_test"


@pytest.fixture()
def store():
    import pymysql

    base = pymysql.connect(
        host="127.0.0.1", user="osap2027", password="2027osapdb", charset="utf8mb4", autocommit=True
    )
    with base.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {TEST_DB}")
    base.close()

    s = OpStore(database=TEST_DB)
    # limpieza de las tablas entre tests
    s._run("DELETE FROM source_suggestions")
    s._run("DELETE FROM providers")
    s._run("DELETE FROM app_config")
    return s


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
