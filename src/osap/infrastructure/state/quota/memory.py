"""Cuotas de descarga (base lógica + almacén en memoria para tests/fallback).

Registra el consumo facturable (OMR) de forma atómica: comprobar y consumir cuota en una
sola operación para que dos peticiones simultáneas no superen el límite. La identidad es el
usuario (registrado) o la IP (visitante).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


def today() -> str:
    return date.today().isoformat()


@dataclass
class QuotaDecision:
    allowed: bool
    identity: str
    used: int
    limit: int | None

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "identity": self.identity,
            "used": self.used,
            "limit": self.limit,
        }


DEFAULT_PLANS: dict[str, int] = {"visitor": 10, "registered": 100, "donor": 1000}


@dataclass
class MemoryStore:
    """Almacén de cuotas en memoria (para tests y como fallback si no hay MySQL)."""

    plans: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_PLANS))
    # user_id -> (limit, valid_from, valid_until|None)
    overrides: dict[str, tuple[int, str | None, str | None]] = field(default_factory=dict)
    counters: dict[tuple[str, str], int] = field(default_factory=dict)
    usage: list[dict[str, object]] = field(default_factory=list)
    # día de referencia conmutable en tests
    current_day: str = field(default_factory=today)

    # ---- resolución de límite ------------------------------------------------
    def plan_limit(self, name: str) -> int | None:
        return self.plans.get(name)

    def override_limit(self, user_id: str | None, day: str) -> int | None:
        if not user_id:
            return None
        row = self.overrides.get(user_id)
        if row is None:
            return None
        limit, valid_from, valid_until = row
        if valid_from and day < valid_from:
            return None
        if valid_until and day > valid_until:
            return None
        return limit

    def _resolve_limit(self, user_id: str | None, is_admin: bool, day: str) -> int | None:
        override = self.override_limit(user_id, day)
        if is_admin:
            # Admin: sin límite salvo que un override fije uno (configurable).
            return override
        if user_id:
            if override is not None:
                return override
            return self.plan_limit("registered")
        return self.plan_limit("visitor")

    # ---- operación atómica (implementada por subclass en MySQL) --------------
    def _atomic_increment(self, day: str, identity_key: str, limit: int) -> bool:
        key = (day, identity_key)
        used = self.counters.get(key, 0)
        if used >= limit:
            return False
        self.counters[key] = used + 1
        return True

    def _used(self, day: str, identity_key: str) -> int:
        return self.counters.get((day, identity_key), 0)

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
        self.usage.append(
            {
                "day": day,
                "user_id": user_id,
                "ip_address": ip,
                "work_id": work_id,
                "resource_id": resource_id,
                "provider": provider,
                "format": fmt,
                "counts_against_plan": 1 if counts_against_plan else 0,
            }
        )

    # ---- API principal -------------------------------------------------------
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
        if limit is None:  # ilimitado (admin sin override)
            self._insert_usage(
                day=day, user_id=user_id, ip=ip, work_id=work_id, resource_id=resource_id,
                provider=provider, fmt=fmt, counts_against_plan=counts_against_plan,
            )
            return QuotaDecision(True, identity_key, self._used(day, identity_key), None)
        if limit <= 0:
            return QuotaDecision(False, identity_key, self._used(day, identity_key), 0)
        if not self._atomic_increment(day, identity_key, limit):
            return QuotaDecision(False, identity_key, self._used(day, identity_key), limit)
        self._insert_usage(
            day=day, user_id=user_id, ip=ip, work_id=work_id, resource_id=resource_id,
            provider=provider, fmt=fmt, counts_against_plan=counts_against_plan,
        )
        return QuotaDecision(True, identity_key, self._used(day, identity_key), limit)

    # ---- administración ------------------------------------------------------
    def set_plan(self, name: str, downloads_per_day: int) -> None:
        self.plans[name] = int(downloads_per_day)

    def set_override(
        self, user_id: str, downloads_per_day: int, valid_from: str | None, valid_until: str | None
    ) -> None:
        self.overrides[user_id] = (int(downloads_per_day), valid_from, valid_until)

    def delete_override(self, user_id: str) -> None:
        self.overrides.pop(user_id, None)

    def list_overrides(self) -> list[dict[str, object]]:
        return [
            {"user_id": uid, "downloads_per_day": lmt, "valid_from": vf, "valid_until": vu}
            for uid, (lmt, vf, vu) in self.overrides.items()
        ]

    def list_plans(self) -> list[dict[str, object]]:
        return [
            {"name": name, "downloads_per_day": limit, "valid_from": None, "valid_until": None}
            for name, limit in self.plans.items()
        ]

    def usage_count(self, day: str, provider: str = "omr") -> int:
        return sum(
            1
            for row in self.usage
            if row["day"] == day and row["provider"] == provider and row["counts_against_plan"]
        )

    def usage_stats(self, from_day: str, to_day: str) -> dict[str, object]:
        """Estadísticas de descargas facturables en [from_day, to_day] (para el panel admin)."""
        rows = [
            r
            for r in self.usage
            if from_day <= str(r["day"]) <= to_day and int(str(r["counts_against_plan"] or 0)) == 1
        ]
        by_day: dict[str, int] = {}
        by_provider: dict[str, int] = {}
        works: dict[str, int] = {}
        users: set[str] = set()
        ips: set[str] = set()
        registered = 0
        for r in rows:
            day = str(r["day"])
            by_day[day] = by_day.get(day, 0) + 1
            provider = str(r["provider"])
            by_provider[provider] = by_provider.get(provider, 0) + 1
            work_id = str(r["work_id"] or "")
            if work_id:
                works[work_id] = works.get(work_id, 0) + 1
            if r["user_id"]:
                registered += 1
                users.add(str(r["user_id"]))
            if r["ip_address"]:
                ips.add(str(r["ip_address"]))
        return {
            "from": from_day,
            "to": to_day,
            "total": len(rows),
            "registered": registered,
            "anonymous": len(rows) - registered,
            "distinct_users": len(users),
            "distinct_ips": len(ips),
            "by_day": [{"day": k, "total": v} for k, v in sorted(by_day.items())],
            "by_provider": [
                {"provider": k, "total": v}
                for k, v in sorted(by_provider.items(), key=lambda x: -x[1])
            ],
            "top_works": [
                {"work_id": k, "total": v}
                for k, v in sorted(works.items(), key=lambda x: -x[1])[:20]
            ],
        }
