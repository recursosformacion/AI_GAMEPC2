"""Almacén de analítica de uso respaldado por MySQL (SQL + schema).

Las tablas viven en la BD operativa de osap-api (mismo `op_store_config`), separadas de
`work_statistics` (valoración, que vive en osap-storage). DDL idempotente al arrancar.
"""

from __future__ import annotations

import pymysql
from pymysql.cursors import DictCursor

from .memory import ANON_USER
from .memory import MemoryStore as _MemoryStore

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS analytics_search_daily (
        day CHAR(10) NOT NULL,
        total INT NOT NULL DEFAULT 0,
        with_results INT NOT NULL DEFAULT 0,
        without_results INT NOT NULL DEFAULT 0,
        PRIMARY KEY (day)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS analytics_consults_daily (
        day CHAR(10) NOT NULL,
        work_id VARCHAR(64) NOT NULL,
        provider VARCHAR(64) NOT NULL DEFAULT '',
        format VARCHAR(32) NOT NULL DEFAULT '',
        consults INT NOT NULL DEFAULT 0,
        PRIMARY KEY (day, work_id, provider, format)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS analytics_downloads (
        day CHAR(10) NOT NULL,
        user_id VARCHAR(64) NOT NULL,
        provider VARCHAR(64) NOT NULL,
        work_id VARCHAR(64) NOT NULL DEFAULT '',
        format VARCHAR(32) NOT NULL DEFAULT '',
        quantity INT NOT NULL DEFAULT 0,
        bytes BIGINT NOT NULL DEFAULT 0,
        PRIMARY KEY (day, user_id, provider, work_id, format)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS analytics_provider_daily (
        day CHAR(10) NOT NULL,
        provider VARCHAR(64) NOT NULL,
        consults INT NOT NULL DEFAULT 0,
        downloads INT NOT NULL DEFAULT 0,
        downloads_failed INT NOT NULL DEFAULT 0,
        osap_acquired INT NOT NULL DEFAULT 0,
        osap_failed INT NOT NULL DEFAULT 0,
        bytes BIGINT NOT NULL DEFAULT 0,
        usable INT NOT NULL DEFAULT 0,
        unusable INT NOT NULL DEFAULT 0,
        PRIMARY KEY (day, provider)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS analytics_catalogue_daily (
        day CHAR(10) NOT NULL,
        works_total INT NOT NULL DEFAULT 0,
        works_with_usable INT NOT NULL DEFAULT 0,
        works_without_usable INT NOT NULL DEFAULT 0,
        PRIMARY KEY (day)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
)


class _MysqlStore(_MemoryStore):
    """Almacén de analítica respaldado por MySQL."""

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        super().__init__()
        self._params = {"host": host, "user": user, "password": password, "database": database}
        self._init()

    def _conn(self) -> pymysql.connections.Connection:
        return pymysql.connect(
            host=self._params["host"],
            user=self._params["user"],
            password=self._params["password"],
            database=self._params["database"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
        )

    def _run(self, sql: str, args: tuple[object, ...] | None = None) -> list[dict[str, object]]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                if cur.description:
                    return [dict(row) for row in cur.fetchall()]
                return []
        finally:
            conn.close()

    def _init(self) -> None:
        for statement in _DDL:
            self._run(statement)

    def record_search(self, day: str, result_total: int) -> None:
        if result_total > 0:
            self.record_search_batch(day, 1, 1, 0)
        else:
            self.record_search_batch(day, 1, 0, 1)

    def record_search_batch(
        self, day: str, total: int, with_results: int, without_results: int
    ) -> None:
        self._run(
            """
            INSERT INTO analytics_search_daily (day, total, with_results, without_results)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                total = total + VALUES(total),
                with_results = with_results + VALUES(with_results),
                without_results = without_results + VALUES(without_results)
            """,
            (day, total, with_results, without_results),
        )

    def record_download(
        self,
        day: str,
        user_id: str,
        provider: str,
        work_id: str,
        fmt: str,
        quantity: int = 1,
        bytes_transferred: int = 0,
    ) -> None:
        self._run(
            """
            INSERT INTO analytics_downloads
                (day, user_id, provider, work_id, format, quantity, bytes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                quantity = quantity + VALUES(quantity),
                bytes = bytes + VALUES(bytes)
            """,
            (day, user_id, provider, work_id, fmt, quantity, bytes_transferred),
        )
        self._run(
            """
            INSERT INTO analytics_provider_daily (day, provider, downloads, bytes)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                downloads = downloads + VALUES(downloads),
                bytes = bytes + VALUES(bytes)
            """,
            (day, provider, quantity, bytes_transferred),
        )

    def record_download_failure(self, day: str, provider: str) -> None:
        self._run(
            """
            INSERT INTO analytics_provider_daily (day, provider, downloads_failed)
            VALUES (%s, %s, 1)
            ON DUPLICATE KEY UPDATE downloads_failed = downloads_failed + 1
            """,
            (day, provider),
        )

    def usage_overview(self, from_day: str, to_day: str) -> dict[str, int]:
        search_rows = self._run(
            """
            SELECT COALESCE(SUM(total), 0) AS total,
                   COALESCE(SUM(with_results), 0) AS with_results,
                   COALESCE(SUM(without_results), 0) AS without_results
            FROM analytics_search_daily
            WHERE day BETWEEN %s AND %s
            """,
            (from_day, to_day),
        )
        download_rows = self._run(
            """
            SELECT COALESCE(SUM(quantity), 0) AS quantity,
                   COALESCE(SUM(bytes), 0) AS bytes,
                   COUNT(DISTINCT CASE WHEN user_id <> %s THEN user_id END) AS users
            FROM analytics_downloads
            WHERE day BETWEEN %s AND %s
            """,
            (ANON_USER, from_day, to_day),
        )
        searches = search_rows[0] if search_rows else {}
        downloads = download_rows[0] if download_rows else {}
        return {
            "searches_total": _as_int(searches.get("total")),
            "searches_with_results": _as_int(searches.get("with_results")),
            "searches_without_results": _as_int(searches.get("without_results")),
            "downloads_total": _as_int(downloads.get("quantity")),
            "downloads_bytes": _as_int(downloads.get("bytes")),
            "downloads_users": _as_int(downloads.get("users")),
        }


def _as_int(value: object) -> int:
    return int(str(value)) if value is not None else 0
