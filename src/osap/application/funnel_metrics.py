"""Métricas del funnel (fase 4.2, paso 7). **Solo lectura y derivación.**

Fuente exclusiva: `funnel_events` + `download_usage`. No se añaden contadores, tablas de
estado ni escrituras. No se exponen IPs.

Diferencia clave:
- **eventos** = `COUNT(*)` (operaciones; p. ej. `promotion_applied` cuenta renovaciones).
- **usuarios** = `COUNT(DISTINCT user_id)` (conversiones; las renovaciones no inflan usuarios).

`limit_reached` se desdobla por stage: `anon_limit_reached` (S1, sin `user_id`) y
`user_limit_reached` (S3, con `user_id`). `promotion_reverted` (revocación admin) se cuenta
por separado de `membership_lapsed` (caducidad).
"""

from __future__ import annotations

_DOWNLOAD_KINDS = ("total", "anonymous", "registered")


class FunnelMetricsUseCase:
    def __init__(self, *, funnel: object, quota: object) -> None:
        self._funnel = funnel
        self._quota = quota

    def metrics(self, from_day: str, to_day: str) -> dict[str, object]:
        events = self._funnel.query_events(from_day, to_day)  # type: ignore[attr-defined]

        def count(event: str, stage: str | None = None) -> int:
            return sum(
                1
                for e in events
                if e["event"] == event and (stage is None or e["stage"] == stage)
            )

        def users(event: str, stage: str | None = None) -> int:
            return len(
                {
                    str(e["user_id"])
                    for e in events
                    if e["event"] == event
                    and (stage is None or e["stage"] == stage)
                    and e["user_id"]
                }
            )

        usage = self._quota.usage_stats(from_day, to_day)  # type: ignore[attr-defined]
        downloads = {k: int(str(usage.get(k) or 0)) for k in _DOWNLOAD_KINDS}

        users_registered = users("registered")
        users_activated = users("membership_activated")
        return {
            "period": {"from": from_day, "to": to_day},
            # Operaciones (COUNT(*)).
            "events": {
                "anon_limit_reached": count("limit_reached", "S1"),
                "registered": count("registered"),
                "user_limit_reached": count("limit_reached", "S3"),
                "membership_activated": count("membership_activated"),
                "membership_lapsed": count("membership_lapsed"),
                "promotion_applied": count("promotion_applied"),
                "promotion_reverted": count("promotion_reverted"),
            },
            # Usuarios únicos (COUNT(DISTINCT user_id)).
            "users": {
                "anon_limit_reached": 0,  # anónimo sin user_id (no se usa la IP)
                "registered": users_registered,
                "user_limit_reached": users("limit_reached", "S3"),
                "membership_activated": users_activated,
                "membership_lapsed": users("membership_lapsed"),
                "promotion_applied": users("promotion_applied"),
                "promotion_reverted": users("promotion_reverted"),
            },
            # Conversiones (usuarios únicos por etapa).
            "conversions": {
                "anon_to_user": users_registered,
                "user_to_donor": users_activated,
            },
            "downloads": {
                "total": downloads["total"],
                "anonymous": downloads["anonymous"],
                "registered": downloads["registered"],
                "by_provider": usage.get("by_provider") or [],
            },
        }
