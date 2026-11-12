from src.osap.application.v6_index import (
    compare_sitemap,
    document_from_feed,
    parse_sitemap_work_url,
)


def test_document_keeps_public_work_id_and_derives_slug():
    document = document_from_feed(
        {
            "work_id": "index-1",
            "title": "I shall be no stranger there",
            "composer": "William James Kirkpatrick",
            "resources": [{"id": 131072, "kind": "score", "file_ids": [624]}],
        }
    )
    assert document.public_id == "index-1"
    assert document.slug == "i-shall-be-no-stranger-there"
    assert document.resources[0]["file_ids"] == [624]


def test_document_accepts_numeric_work_id_but_normalizes_public_id():
    document = document_from_feed({"work_id": "42", "title": "Ave verum"})
    assert document.public_id == "index-42"
    assert document.slug == "ave-verum"


def test_compare_sitemap_distinguishes_canonical_historical_and_missing():
    documents = {
        "index-1": document_from_feed(
            {"work_id": "index-1", "title": "I shall be no stranger there"}
        )
    }
    result = compare_sitemap(
        [
            "https://app.example/obras/index-1/i-shall-be-no-stranger-there",
            "https://app.example/obras/index-1/i-shall-be-no-stranger-there-william-j-kirkpatrick",
            "https://app.example/obras/index-9/otra-obra",
            "https://app.example/otra-ruta",
        ],
        documents,
    )
    assert result["checked"] == 2
    assert result["canonical_match"] == 1
    assert result["historical_slug"] == 1
    assert result["missing_document"] == 1
    assert result["malformed"] == 1


def test_parse_sitemap_work_url():
    assert parse_sitemap_work_url(
        "https://app.example/obras/index-7/ave-verum"
    ) == ("index-7", "ave-verum")
    assert parse_sitemap_work_url("https://app.example/composers/x/y") is None
