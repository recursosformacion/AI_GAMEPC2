"""Reconciliador de membresía → cuota donor (fase 4.2, paso 5).

`osap-support` es la fuente de verdad: si dice `active=true` y `tier=donor`, este caso de uso
materializa un **override** en `user_quota_overrides` (1000/día) con la **vigencia exacta**
recibida; si deja de estar activa, retira el override. **No interpreta pagos.**

Reglas:
- Idempotente: repetir con el mismo estado no duplica ni genera overrides equivalentes.
- Renovación/cambio de vigencia: se **actualiza** el mismo override (no se acumulan).
- Fallo de consulta (support no responde) ≠ inactivo: **no** se retira ni se emite nada.
- No toca `download_quota_daily` ni el circuito de descarga.
- Eventos (append-only): `membership_activated` y `promotion_applied` al materializar;
  `membership_lapsed` al dejar de estar activa.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable


class SupportUnavailableError(Exception):
    """osap-support no respondió o devolvió un error: NO implica inactividad."""


@dataclass(frozen=True)
class MembershipSnapshot:
    """Estado de membresía tal como lo devuelve el contrato M2M (fuente de verdad)."""

    active: bool
    tier: str | None = None
    valid_from: datetime | date | str | None = None
    valid_until: datetime | date | str | None = None
    source: str | None = None


class MembershipSource(Protocol):
    def fetch(self, user_id: str) -> MembershipSnapshot: ...


DONOR_LIMIT = 1000
_DONOR_TIER = "donor"


def _day(value: object) -> str | None:
    """Normaliza a `YYYY-MM-DD` (datetime/date/str); None si no hay valor."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


class ReconcileMembershipUseCase:
    """Aplica/retira overrides donor según la membresía de `osap-support`."""

    def __init__(self, *, source: MembershipSource, quota: object, funnel: object) -> None:
        self._source = source
        self._quota = quota
        self._funnel = funnel

    # ---- estado actual --------------------------------------------------------
    def _current_overrides(self) -> dict[str, dict[str, object]]:
        rows = self._quota.list_overrides()  # type: ignore[attr-defined]
        return {str(r["user_id"]): dict(r) for r in rows}

    def _override_matches(self, current: dict[str, object], limit: int, vf: str | None, vu: str | None) -> bool:
        return (
            int(str(current.get("downloads_per_day") or 0)) == limit
            and _day(current.get("valid_from")) == vf
            and _day(current.get("valid_until")) == vu
        )

    # ---- reconciliación de un usuario ----------------------------------------
    def reconcile_user(self, user_id: str) -> str:
        """Devuelve: applied | updated | lapsed | noop | skipped."""
        try:
            snap = self._source.fetch(user_id)
        except SupportUnavailableError:
            return "skipped"  # consulta no fiable: no se toca nada
        except Exception:  # noqa: BLE001 — ante cualquier duda, no cambiar cuota
            return "skipped"

        current = self._current_overrides().get(user_id)
        promote = snap.active and snap.tier == _DONOR_TIER
        if promote:
            vf = _day(snap.valid_from)
            vu = _day(snap.valid_until)
            if current is None:
                self._apply(user_id, vf, vu, snap.source)
                self._event("membership_activated", "S4", user_id, snap)
                self._event("promotion_applied", "S4", user_id, snap)
                return "applied"
            if self._override_matches(current, DONOR_LIMIT, vf, vu):
                return "noop"  # idempotente: mismo estado
            # renovación / cambio de vigencia: se actualiza el MISMO override
            self._apply(user_id, vf, vu, snap.source)
            self._event("promotion_applied", "S4", user_id, snap)
            return "updated"
        # No promocionable (inactiva o tier != donor): retirar si existía.
        if current is not None:
            self._quota.delete_override(user_id)  # type: ignore[attr-defined]
            self._event("membership_lapsed", "S2", user_id, snap)
            return "lapsed"
        return "noop"

    def _apply(self, user_id: str, vf: str | None, vu: str | None, source: str | None) -> None:
        note = f"membership:{source}" if source else "membership"
        store = self._quota
        try:
            store.set_override(user_id, DONOR_LIMIT, vf, vu, note)  # type: ignore[attr-defined]
        except TypeError:  # almacén en memoria sin `note`
            store.set_override(user_id, DONOR_LIMIT, vf, vu)  # type: ignore[attr-defined]

    def _event(self, event: str, stage: str, user_id: str, snap: MembershipSnapshot) -> None:
        try:
            self._funnel.record_event(  # type: ignore[attr-defined]
                event,
                stage=stage,
                user_id=user_id,
                detail={
                    "tier": snap.tier,
                    "valid_from": _day(snap.valid_from),
                    "valid_until": _day(snap.valid_until),
                    "source": snap.source,
                },
            )
        except Exception:  # noqa: BLE001 — el histórico no debe romper la reconciliación
            return

    # ---- reconciliación por lotes --------------------------------------------
    def reconcile(self, user_ids: Iterable[str]) -> dict[str, int]:
        summary = {"applied": 0, "updated": 0, "lapsed": 0, "noop": 0, "skipped": 0}
        for user_id in user_ids:
            try:
                outcome = self.reconcile_user(user_id)
            except Exception:  # noqa: BLE001 — un usuario no debe abortar el lote
                outcome = "skipped"
            summary[outcome] = summary.get(outcome, 0) + 1
        return summary
