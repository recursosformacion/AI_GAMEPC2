import pytest

from src.osap.infrastructure.state.op_store import build_op_store

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

    conn = pymysql.connect(
        host="127.0.0.1", user="osap2027", password="2027osapdb", database=TEST_DB, charset="utf8mb4", autocommit=True
    )
    with conn.cursor() as cur:
        for table in ("source_suggestions", "providers", "app_config"):
            cur.execute(f"DELETE FROM {table}")
    conn.close()

    return build_op_store(database=TEST_DB)


def test_suggestion_roundtrip(store) -> None:
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


def test_provider_upsert_and_wired(store) -> None:
    store.upsert_provider("prov-x", "Provider X", base_url="https://x", wired=False, config={"k": "v"})
    assert store.get_provider("prov-x")["wired"] == 0
    store.set_provider_wired("prov-x", True)
    assert store.get_provider("prov-x")["wired"] == 1


def test_provider_description_and_delete(store) -> None:
    row = store.upsert_provider(
        "prov-desc",
        "Provider Desc",
        base_url="https://x",
        wired=True,
        config={"endpoint": "https://x/search"},
        description={"en": "Test directory", "es": "Directorio de prueba"},
        endpoints={"search": {"path": "/search"}},
        mapping={"work": {"id": "id"}},
        transforms={"fields": {}},
    )
    assert row["description"] == {"en": "Test directory", "es": "Directorio de prueba"}
    assert row["endpoints"] == {"search": {"path": "/search"}}
    got = store.get_provider("prov-desc")
    assert got is not None
    assert got["description"] == {"en": "Test directory", "es": "Directorio de prueba"}
    assert got["mapping"] == {"work": {"id": "id"}}
    assert store.delete_provider("prov-desc") is True
    assert store.get_provider("prov-desc") is None
    assert store.delete_provider("prov-desc") is False


def test_app_config(store) -> None:
    assert store.get_config("missing") is None
    store.set_config("theme", "dark")
    assert store.get_config("theme") == "dark"
    store.set_config("theme", "light")
    assert store.get_config("theme") == "light"
