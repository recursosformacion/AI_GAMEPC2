from script.export_api_schema_inventory import _render, _safe_default


def test_schema_export_redacts_sensitive_column_defaults() -> None:
    assert _safe_default("client_secret", "example-secret") == "[REDACTED]"
    assert _safe_default("api_token", "example-token") == "[REDACTED]"
    assert _safe_default("display_name", "OSAP") == "OSAP"


def test_schema_export_includes_table_and_column_inventory() -> None:
    markdown = _render(
        "osap_api",
        [{"TABLE_NAME": "app_config", "ENGINE": "InnoDB", "TABLE_ROWS": 3, "TABLE_COMMENT": ""}],
        [{
            "TABLE_NAME": "app_config",
            "COLUMN_NAME": "client_secret",
            "ORDINAL_POSITION": 1,
            "COLUMN_TYPE": "varchar(255)",
            "IS_NULLABLE": "YES",
            "COLUMN_DEFAULT": "example-secret",
            "COLUMN_KEY": "",
            "EXTRA": "",
            "COLUMN_COMMENT": "",
        }],
        [],
        [],
    )

    assert "app_config" in markdown
    assert "varchar(255)" in markdown
    assert "[REDACTED]" in markdown
    assert "example-secret" not in markdown
