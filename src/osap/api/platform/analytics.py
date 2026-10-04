"""PlatformApi: mixin de analítica de uso (estadísticas de uso y proveedores)."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.osap.api.platform.core import PlatformApiCore
from src.osap.infrastructure.state.analytics.memory import today

_LOGGER = logging.getLogger("osap.analytics")

VERSION = "3.1"


class AnalyticsMixin(PlatformApiCore):
    """Registro no bloqueante de eventos de uso y consulta agregada (admin)."""

    def record_search_event(self, result_total: int) -> None:
        """Cuenta una búsqueda completada (una por llamada; el cache hit también cuenta)."""
        try:
            self._analytics.record_search(result_total)
        except Exception:  # noqa: BLE001 — la analítica nunca rompe la petición
            _LOGGER.warning("No se pudo registrar la búsqueda", exc_info=True)

    def record_download_event(
        self,
        *,
        provider: str,
        work_id: str,
        fmt: str,
        user_id: str | None = None,
        bytes_transferred: int = 0,
    ) -> None:
        """Cuenta una solicitud de descarga iniciada desde OSAP (con usuario y proveedor)."""
        try:
            self._analytics.record_download(
                provider=provider,
                work_id=work_id,
                fmt=fmt,
                user_id=user_id,
                bytes_transferred=bytes_transferred,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning("No se pudo registrar la descarga", exc_info=True)

    def record_download_failure_event(self, *, provider: str) -> None:
        """Cuenta una descarga fallida (upstream no sirvió el fichero)."""
        try:
            self._analytics.record_download_failure(provider)
        except Exception:  # noqa: BLE001
            _LOGGER.warning("No se pudo registrar el fallo de descarga", exc_info=True)

    def analytics_overview(self, from_day: str, to_day: str) -> dict[str, int]:
        """Vuelca el buffer y devuelve los agregados del rango [from_day, to_day]."""
        try:
            self._analytics.flush()
        except Exception:  # noqa: BLE001 — leer no debe fallar por un flush
            _LOGGER.warning("No se pudo volcar la analítica antes de leer", exc_info=True)
        return self._analytics_store.usage_overview(from_day, to_day)

    def analytics_me(
        self, token: str | None, from_day: str | None, to_day: str | None
    ) -> dict[str, object] | None:
        """Estadísticas del propio usuario (identidad del token; nunca del cliente).

        Devuelve `None` si no hay usuario autenticado. Solo agrega filas ya existentes
        (`analytics_downloads` por `user_id`, cuota del día y plan/override vigente).
        """
        principal = self.current_user(token)
        user_id = getattr(principal, "user_id", None)
        if not user_id:
            return None
        day = today()
        start = from_day or day
        end = to_day or day
        if start > end:
            start, end = end, start
        try:
            self._analytics.flush()
        except Exception:  # noqa: BLE001
            _LOGGER.warning("No se pudo volcar la analítica antes de leer", exc_info=True)
        downloads = self._analytics_store.usage_for_user(str(user_id), start, end)
        quota = self._quota_store.status_for_user(str(user_id), day)  # type: ignore[attr-defined]
        limit = int(quota.get("limit") or 0)
        used = int(quota.get("used") or 0)
        donor = bool(quota.get("donor"))
        stage = "S4" if donor else ("S3" if limit and used >= limit else "S2")
        return {
            "period": {"from_day": start, "to_day": end},
            "access": {"stage": stage, "tier": str(quota.get("tier") or "registered")},
            "quota": {
                "limit": limit,
                "used": used,
                "remaining": int(quota.get("remaining") or 0),
            },
            "downloads": downloads,
        }

    def activity_me(
        self, token: str | None, from_day: str | None, to_day: str | None
    ) -> dict[str, object] | None:
        """Panel personal de actividad («Mi Actividad»).

        Compone, sin métricas nuevas: descargas/cuota (`analytics_me`), aportaciones propias
        (`contributions`), pendientes, descargas detalladas e impacto (uso de las obras de las
        aportaciones materializadas). `None` si no hay usuario autenticado.
        """
        principal = self.current_user(token)
        user_id = getattr(principal, "user_id", None)
        if not user_id:
            return None
        base = self.analytics_me(token, from_day, to_day)
        if base is None:
            return None
        uid = str(user_id)
        rows, total = self._store.list_contributions_by_actor(uid, limit=100, offset=0)
        contribs = [self._contribution_brief(r) for r in rows]
        pending = [c for c in contribs if str(c["status"]) in ("draft", "submitted", "in_review")]
        try:
            self._analytics.flush()
        except Exception:  # noqa: BLE001
            _LOGGER.warning("No se pudo volcar la analítica antes de leer", exc_info=True)
        downloads = base.get("downloads")
        downloads = downloads if isinstance(downloads, dict) else {}
        summary = {
            "downloads": int(str(downloads.get("count", 0))),
            "bytes": int(str(downloads.get("bytes", 0))),
            "contributions_total": int(total),
            "contributions_accepted": sum(1 for c in contribs if c["status"] == "accepted"),
            "contributions_pending": len(pending),
            "works": len(
                {
                    str(c["target_id"])
                    for c in contribs
                    if c["status"] == "accepted" and c["target_id"]
                }
            ),
        }
        return {
            "user_id": uid,
            "period": base["period"],
            "access": base["access"],
            "quota": base["quota"],
            "summary": summary,
            "my_downloads": self._analytics_store.list_user_downloads(uid, limit=50),
            "my_contributions": contribs,
            "pending": pending,
            "impact": self._impact(rows),
            "recent": self._recent(rows),
        }

    @staticmethod
    def _contribution_brief(row: dict[str, object]) -> dict[str, object]:
        return {
            "id": int(str(row["id"])),
            "operation": str(row["operation"]),
            "target_kind": str(row["target_kind"]),
            "target_id": str(row["target_id"]) if row.get("target_id") else None,
            "status": str(row["status"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def _impact(self, rows: list[dict[str, object]]) -> dict[str, object]:
        work_ids: set[str] = set()
        for row in rows:
            cid = int(str(row["id"]))
            for event in self._store.list_contribution_events(cid):
                if str(event.get("event_type")) != "materialized":
                    continue
                try:
                    detail = json.loads(str(event.get("detail_json") or "{}"))
                except ValueError:
                    continue
                if isinstance(detail, dict) and detail.get("work_id") is not None:
                    work_ids.add(str(detail["work_id"]))
        return self._analytics_store.downloads_for_works(sorted(work_ids))

    def _recent(self, rows: list[dict[str, object]], limit: int = 20) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for row in rows:
            cid = int(str(row["id"]))
            for event in self._store.list_contribution_events(cid):
                items.append(
                    {
                        "at": str(event.get("created_at")),
                        "kind": f"contribution:{event.get('event_type')}",
                        "contribution_id": cid,
                        "status": str(event.get("to_status") or ""),
                    }
                )
        items.sort(key=lambda item: str(item["at"]), reverse=True)
        return items[:limit]
