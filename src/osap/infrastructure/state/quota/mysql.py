"""Cuotas de descarga respaldadas por MySQL (BD de osap-api)."""

from __future__ import annotations

from datetime import date

import pymysql
from pymysql.cursors import DictCursor

from .memory import DEFAULT_PLANS, MemoryStore, QuotaDecision

_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS download_plans (
        name VARCHAR(32) NOT NULL,
        downloads_per_day INT NOT NULL,
        valid_from DATE NULL,
        valid_until DATE NULL,
        updated_at DATETIME(6) NOT NULL,
        PRIMARY KEY (name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS user_quota_overrides (
        user_id VARCHAR(64) NOT NULL,
        downloads_per_day INT NOT NULL,
        valid_from DATE NULL,
        valid_until DATE NULL,
        note VARCHAR(255) NULL,
        updated_at DATETIME(6) NOT NULL,
        PRIMARY KEY (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS download_quota_daily (
        day CHAR(10) NOT NULL,
        identity_key VARCHAR(128) NOT NULL,
        used INT NOT NULL DEFAULT 0,
        PRIMARY KEY (day, identity_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS download_usage (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        created_at DATETIME(6) NOT NULL,
        day CHAR(10) NOT NULL,
        user_id VARCHAR(64) NULL,
        ip_address VARCHAR(45) NULL,
        work_id VARCHAR(64) NULL,
        resource_id BIGINT UNSIGNED NULL,
        provider VARCHAR(32) NOT NULL,
        format VARCHAR(32) NULL,
        counts_against_plan TINYINT NOT NULL DEFAULT 1,
        PRIMARY KEY (id),
        KEY idx_usage_day (day),
        KEY idx_usage_user (user_id, day),
        KEY idx_usage_ip (ip_address, day)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
) + tuple(
    f"INSERT INTO download_plans (name, downloads_per_day, valid_from, valid_until, updated_at) "
    f"VALUES ('{name}', {limit}, NULL, NULL, NOW(6)) ON DUPLICATE KEY UPDATE name = name"
    for name, limit in DEFAULT_PLANS.items()
)


class _MysqlStore(MemoryStore):
    """Cuotas en MySQL. `consume` es atómico (incremento + registro en una transacción)."""

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        super().__init__()
        self._params = {"host": host, "user": user, "password": password, "database": database}
        for statement in _DDL:
            self._run(statement)

    def _conn(self, *, autocommit: bool = True) -> pymysql.connections.Connection:
        return pymysql.connect(
            host=self._params["host"],
            user=self._params["user"],
            password=self._params["password"],
            database=self._params["database"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=autocommit,
            ssl_disabled=str(self._params["host"]) in ("127.0.0.1", "localhost"),
        )

    def _run(self, sql: str, args: tuple[object, ...] | None = None) -> list[dict[str, object]]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [dict(row) for row in cur.fetchall()] if cur.description else []
        finally:
            conn.close()

    # ---- resolución de límite ------------------------------------------------
    def plan_limit(self, name: str) -> int | None:
        rows = self._run(
            "SELECT downloads_per_day FROM download_plans WHERE name = %s "
            "AND (valid_from IS NULL OR valid_from <= CURDATE()) "
            "AND (valid_until IS NULL OR valid_until >= CURDATE())",
            (name,),
        )
        return int(str(rows[0]["downloads_per_day"])) if rows else None

    def override_limit(self, user_id: str | None, day: str) -> int | None:
        if not user_id:
            return None
        rows = self._run(
            "SELECT downloads_per_day FROM user_quota_overrides WHERE user_id = %s "
            "AND (valid_from IS NULL OR valid_from <= %s) "
            "AND (valid_until IS NULL OR valid_until >= %s)",
            (user_id, day, day),
        )
        return int(str(rows[0]["downloads_per_day"])) if rows else None

    def _used(self, day: str, identity_key: str) -> int:
        rows = self._run(
            "SELECT used FROM download_quota_daily WHERE day = %s AND identity_key = %s",
            (day, identity_key),
        )
        return int(str(rows[0]["used"])) if rows else 0

    def _insert_usage(
        self,
        *,
        day: str,
        user_id: str | None,
        ip: str | None,
        work_id: str | None,
        resource_id: int | None,
        provider: str,
        fmt: str | None,
        counts_against_plan: bool,
    ) -> None:
        self._run(
            "INSERT INTO download_usage (created_at, day, user_id, ip_address, work_id, "
            "resource_id, provider, format, counts_against_plan) "
            "VALUES (NOW(6), %s, %s, %s, %s, %s, %s, %s, %s)",
            (day, user_id, ip, work_id, resource_id, provider, fmt, 1 if counts_against_plan else 0),
        )

    def consume(
        self,
        *,
        day: str,
        user_id: str | None,
        ip: str | None,
        is_admin: bool,
        work_id: str | None,
        resource_id: int | None,
        provider: str,
        fmt: str | None,
        counts_against_plan: bool = True,
    ) -> QuotaDecision:
        identity_key = f"u:{user_id}" if user_id else f"ip:{ip or 'unknown'}"
        limit = self._resolve_limit(user_id, is_admin, day)
        if limit is not None and limit <= 0:
            return QuotaDecision(False, identity_key, self._used(day, identity_key), 0)
        if limit is None:  # ilimitado (admin sin override)
            self._insert_usage(
                day=day, user_id=user_id, ip=ip, work_id=work_id, resource_id=resource_id,
                provider=provider, fmt=fmt, counts_against_plan=counts_against_plan,
            )
            return QuotaDecision(True, identity_key, self._used(day, identity_key), None)

        conn = self._conn(autocommit=False)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO download_quota_daily (day, identity_key, used) VALUES (%s, %s, 1) "
                    "ON DUPLICATE KEY UPDATE used = IF(used < %s, used + 1, used)",
                    (day, identity_key, limit),
                )
                allowed = cur.rowcount in (1, 2)
                if allowed:
                    cur.execute(
                        "INSERT INTO download_usage (created_at, day, user_id, ip_address, work_id, "
                        "resource_id, provider, format, counts_against_plan) "
                        "VALUES (NOW(6), %s, %s, %s, %s, %s, %s, %s, %s)",
                        (day, user_id, ip, work_id, resource_id, provider, fmt,
                         1 if counts_against_plan else 0),
                    )
            if allowed:
                conn.commit()
            else:
                conn.rollback()
        finally:
            conn.close()
        return QuotaDecision(allowed, identity_key, self._used(day, identity_key), limit)

    # ---- administración ------------------------------------------------------
    def set_plan(
        self,
        name: str,
        downloads_per_day: int,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> None:
        self._run(
            "INSERT INTO download_plans (name, downloads_per_day, valid_from, valid_until, updated_at) "
            "VALUES (%s, %s, %s, %s, NOW(6)) ON DUPLICATE KEY UPDATE "
            "downloads_per_day = VALUES(downloads_per_day), valid_from = VALUES(valid_from), "
            "valid_until = VALUES(valid_until), updated_at = NOW(6)",
            (name, int(downloads_per_day), valid_from, valid_until),
        )

    def set_override(
        self,
        user_id: str,
        downloads_per_day: int,
        valid_from: str | None,
        valid_until: str | None,
        note: str | None = None,
    ) -> None:
        self._run(
            "INSERT INTO user_quota_overrides (user_id, downloads_per_day, valid_from, valid_until, "
            "note, updated_at) VALUES (%s, %s, %s, %s, %s, NOW(6)) ON DUPLICATE KEY UPDATE "
            "downloads_per_day = VALUES(downloads_per_day), valid_from = VALUES(valid_from), "
            "valid_until = VALUES(valid_until), note = VALUES(note), updated_at = NOW(6)",
            (user_id, int(downloads_per_day), valid_from, valid_until, note),
        )

    def delete_override(self, user_id: str) -> None:
        self._run("DELETE FROM user_quota_overrides WHERE user_id = %s", (user_id,))

    def list_overrides(self) -> list[dict[str, object]]:
        return self._run(
            "SELECT user_id, downloads_per_day, valid_from, valid_until, note "
            "FROM user_quota_overrides ORDER BY user_id"
        )

    def list_plans(self) -> list[dict[str, object]]:
        return self._run(
            "SELECT name, downloads_per_day, valid_from, valid_until FROM download_plans ORDER BY name"
        )

    def usage_stats(self, from_day: str, to_day: str) -> dict[str, object]:
        base = "FROM download_usage WHERE counts_against_plan = 1 AND day BETWEEN %s AND %s"
        args = (from_day, to_day)
        total = self._run(f"SELECT COUNT(*) AS n {base}", args)[0]["n"]
        by_day = self._run(
            f"SELECT day, COUNT(*) AS total {base} GROUP BY day ORDER BY day", args
        )
        by_provider = self._run(
            f"SELECT provider, COUNT(*) AS total {base} GROUP BY provider ORDER BY total DESC", args
        )
        top_works = self._run(
            f"SELECT work_id, COUNT(*) AS total {base} AND work_id IS NOT NULL "
            "GROUP BY work_id ORDER BY total DESC LIMIT 20",
            args,
        )
        split = self._run(
            "SELECT COUNT(DISTINCT user_id) AS users, COUNT(DISTINCT ip_address) AS ips, "
            "SUM(user_id IS NOT NULL) AS registered "
            f"{base}",
            args,
        )[0]
        registered = int(str(split["registered"] or 0))
        return {
            "from": from_day,
            "to": to_day,
            "total": int(str(total)),
            "registered": registered,
            "anonymous": int(str(total)) - registered,
            "distinct_users": int(str(split["users"] or 0)),
            "distinct_ips": int(str(split["ips"] or 0)),
            "by_day": [{"day": str(r["day"]), "total": int(str(r["total"]))} for r in by_day],
            "by_provider": [
                {"provider": str(r["provider"]), "total": int(str(r["total"]))} for r in by_provider
            ],
            "top_works": [
                {"work_id": str(r["work_id"]), "total": int(str(r["total"]))} for r in top_works
            ],
        }


def default_day() -> str:
    return date.today().isoformat()
