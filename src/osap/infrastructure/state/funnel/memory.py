"""Eventos del funnel (fase 4.2): base lógica + almacén en memoria.

`funnel_events` es **append-only**: solo se añaden eventos, nunca se modifican ni borran.
Registra los hitos del funnel (límite alcanzado, registro, membresía y promociones)
**sin tocar** el store de cuota ni el circuito de descarga: el funnel observa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum, StrEnum


class FunnelEvent(StrEnum):
    """Tipos de evento del funnel (contrato 4.2)."""

    LIMIT_REACHED = "limit_reached"
    REGISTERED = "registered"
    MEMBERSHIP_ACTIVATED = "membership_activated"
    MEMBERSHIP_LAPSED = "membership_lapsed"
    PROMOTION_APPLIED = "promotion_applied"
    PROMOTION_REVERTED = "promotion_reverted"


class FunnelStage(StrEnum):
    """Estados del funnel (contrato 4.2)."""

    S1 = "S1"  # anónimo con límite agotado
    S2 = "S2"  # registrado
    S3 = "S3"  # registrado con límite agotado
    S4 = "S4"  # donor


def today() -> str:
    return date.today().isoformat()


def _value(value: object | None) -> str | None:
    if value is None:
        return None
    return value.value if isinstance(value, Enum) else str(value)


@dataclass
class MemoryStore:
    """Almacén de eventos en memoria (tests/fallback). Append-only por diseño."""

    events: list[dict[str, object]] = field(default_factory=list)

    def record_event(
        self,
        event: FunnelEvent,
        *,
        stage: FunnelStage | None = None,
        user_id: str | None = None,
        ip_address: str | None = None,
        override_id: int | None = None,
        detail: dict[str, object] | None = None,
        day: str | None = None,
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "event": _value(event),
            "stage": _value(stage),
            "user_id": user_id,
            "ip_address": ip_address,
            "override_id": override_id,
            "detail": dict(detail) if detail else None,
            "day": day or today(),
        }
        self.events.append(row)
        return row

    def count(self, event: FunnelEvent | None = None, day: str | None = None) -> int:
        return sum(
            1
            for r in self.events
            if (event is None or r["event"] == _value(event)) and (day is None or r["day"] == day)
        )

    def reverted_periods(self, user_id: str) -> set[str]:
        """`valid_from` de los periodos con `promotion_reverted` (revocación manual).

        El reconciliador lo usa para NO resucitar una promoción revocada dentro del mismo
        periodo de membresía (una revocación administrativa no se deshace sola).
        """
        out: set[str] = set()
        for r in self.events:
            if r["user_id"] != user_id or r["event"] != FunnelEvent.PROMOTION_REVERTED.value:
                continue
            detail = r.get("detail")
            if isinstance(detail, dict) and detail.get("valid_from"):
                out.add(str(detail["valid_from"])[:10])
        return out

    def has_event(self, user_id: str, event: FunnelEvent) -> bool:
        """True si ya existe ese evento para el usuario (guarda de idempotencia)."""
        return any(
            r["user_id"] == user_id and r["event"] == _value(event) for r in self.events
        )

    def events_for_user(self, user_id: str, day: str | None = None) -> list[dict[str, object]]:
        return [
            r
            for r in self.events
            if r["user_id"] == user_id and (day is None or r["day"] == day)
        ]
