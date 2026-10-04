"""Almacén de analítica de uso en memoria (fallback cuando MySQL no está disponible).

Mantiene los mismos contadores que la versión MySQL: agregados diarios de búsquedas,
descargas (dimensión usuario+proveedor+día) y agregados diarios por proveedor.
"""

from __future__ import annotations

from datetime import UTC, datetime

ANON_USER = "anon"


def today() -> str:
    """Día UTC en formato YYYY-MM-DD (mismo criterio que `vote_day`)."""
    return datetime.now(UTC).date().isoformat()


class MemoryStore:
    """Almacén de analítica en memoria con la misma interfaz que la versión MySQL."""

    def __init__(self) -> None:
        # day -> {total, with_results, without_results}
        self._search_daily: dict[str, dict[str, int]] = {}
        # (day, user_id, provider, work_id, format) -> {quantity, bytes}
        self._downloads: dict[tuple[str, str, str, str, str], dict[str, int]] = {}
        # (day, provider) -> contadores agregados
        self._provider_daily: dict[tuple[str, str], dict[str, int]] = {}

    @staticmethod
    def _provider_row() -> dict[str, int]:
        return {
            "consults": 0,
            "downloads": 0,
            "downloads_failed": 0,
            "osap_acquired": 0,
            "osap_failed": 0,
            "bytes": 0,
            "usable": 0,
            "unusable": 0,
        }

    def record_search(self, day: str, result_total: int) -> None:
        if result_total > 0:
            self.record_search_batch(day, 1, 1, 0)
        else:
            self.record_search_batch(day, 1, 0, 1)

    def record_search_batch(
        self, day: str, total: int, with_results: int, without_results: int
    ) -> None:
        row = self._search_daily.setdefault(
            day, {"total": 0, "with_results": 0, "without_results": 0}
        )
        row["total"] += total
        row["with_results"] += with_results
        row["without_results"] += without_results

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
        key = (day, user_id, provider, work_id, fmt)
        row = self._downloads.setdefault(key, {"quantity": 0, "bytes": 0})
        row["quantity"] += quantity
        row["bytes"] += bytes_transferred
        provider_row = self._provider_daily.setdefault((day, provider), self._provider_row())
        provider_row["downloads"] += quantity
        provider_row["bytes"] += bytes_transferred

    def record_download_failure(self, day: str, provider: str) -> None:
        provider_row = self._provider_daily.setdefault((day, provider), self._provider_row())
        provider_row["downloads_failed"] += 1

    def usage_for_user(self, user_id: str, from_day: str, to_day: str) -> dict[str, object]:
        """Descargas del propio usuario en [from_day, to_day] (dimensión usuario).

        Devuelve `{count, bytes, providers: [{provider, downloads, bytes}]}`. Solo lectura de
        las filas ya existentes; no introduce métricas nuevas.
        """
        count = 0
        bytes_total = 0
        by_provider: dict[str, dict[str, int]] = {}
        for (day, uid, provider, _work, _fmt), row in self._downloads.items():
            if uid != user_id or not (from_day <= day <= to_day):
                continue
            count += row["quantity"]
            bytes_total += row["bytes"]
            bucket = by_provider.setdefault(provider, {"downloads": 0, "bytes": 0})
            bucket["downloads"] += row["quantity"]
            bucket["bytes"] += row["bytes"]
        providers = [
            {"provider": name, "downloads": data["downloads"], "bytes": data["bytes"]}
            for name, data in sorted(by_provider.items())
        ]
        return {"count": count, "bytes": bytes_total, "providers": providers}

    def list_user_downloads(self, user_id: str, limit: int = 50) -> list[dict[str, object]]:
        agg: dict[tuple[str, str, str, str], dict[str, int]] = {}
        for (day, uid, provider, work, fmt), row in self._downloads.items():
            if uid != user_id:
                continue
            bucket = agg.setdefault((day, provider, work, fmt), {"quantity": 0, "bytes": 0})
            bucket["quantity"] += row["quantity"]
            bucket["bytes"] += row["bytes"]
        items = [
            {"day": day, "provider": provider, "work_id": work, "format": fmt,
             "quantity": data["quantity"], "bytes": data["bytes"]}
            for (day, provider, work, fmt), data in agg.items()
        ]
        items.sort(key=lambda x: (str(x["day"]), int(str(x["quantity"]))), reverse=True)
        return items[:limit]

    def downloads_for_works(self, work_ids: list[str]) -> dict[str, object]:
        wanted = set(work_ids)
        total = 0
        bytes_total = 0
        by_work: dict[str, int] = {}
        for (_day, _uid, _p, work, _fmt), row in self._downloads.items():
            if work in wanted:
                total += row["quantity"]
                bytes_total += row["bytes"]
                by_work[work] = by_work.get(work, 0) + row["quantity"]
        works = [
            {"work_id": work, "downloads": count, "bytes": 0}
            for work, count in sorted(by_work.items(), key=lambda kv: -kv[1])
        ]
        return {"downloads": total, "bytes": bytes_total, "works": works}

    def usage_overview(self, from_day: str, to_day: str) -> dict[str, int]:
        searches_total = 0
        searches_with = 0
        searches_without = 0
        for day, row in self._search_daily.items():
            if from_day <= day <= to_day:
                searches_total += row["total"]
                searches_with += row["with_results"]
                searches_without += row["without_results"]
        downloads_total = 0
        downloads_bytes = 0
        users: set[str] = set()
        for (day, user_id, _provider, _work, _fmt), row in self._downloads.items():
            if from_day <= day <= to_day:
                downloads_total += row["quantity"]
                downloads_bytes += row["bytes"]
                if user_id != ANON_USER:
                    users.add(user_id)
        return {
            "searches_total": searches_total,
            "searches_with_results": searches_with,
            "searches_without_results": searches_without,
            "downloads_total": downloads_total,
            "downloads_bytes": downloads_bytes,
            "downloads_users": len(users),
        }
