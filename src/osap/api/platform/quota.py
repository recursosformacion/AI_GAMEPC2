"""PlatformApi: mixin de cuotas de descarga OMR (plan + override + consumo atómico)."""

from __future__ import annotations

import logging

from src.osap.api.platform.core import PlatformApiCore
from src.osap.infrastructure.state.quota.memory import QuotaDecision, today

_LOGGER = logging.getLogger("osap.quota")


class QuotaMixin(PlatformApiCore):
    """Comprueba y consume cuota de descarga facturable (OMR) y gestiona planes/overrides."""

    def consume_omr_download(
        self,
        *,
        user_id: str | None,
        ip: str | None,
        is_admin: bool,
        work_id: str | None,
        resource_id: int | None,
        fmt: str | None,
    ) -> QuotaDecision:
        """Consume 1 descarga OMR del usuario/IP para hoy (atómico) y devuelve la decisión."""
        store = self._quota_store
        return store.consume(  # type: ignore[attr-defined, no-any-return]
            day=today(),
            user_id=user_id,
            ip=ip,
            is_admin=is_admin,
            work_id=work_id,
            resource_id=resource_id,
            provider="omr",
            fmt=fmt,
            counts_against_plan=True,
        )

    # --- administración de planes y excepciones (role=admin) ------------------

    def quota_plans(self, token: str | None) -> list[dict[str, object]]:
        self._require_admin(token)
        return self._quota_store.list_plans()  # type: ignore[attr-defined, no-any-return]

    def quota_set_plan(
        self,
        token: str | None,
        name: str,
        downloads_per_day: int,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> None:
        self._require_admin(token)
        self._quota_store.set_plan(name, downloads_per_day, valid_from, valid_until)  # type: ignore[attr-defined]

    def quota_overrides(self, token: str | None) -> list[dict[str, object]]:
        self._require_admin(token)
        return self._quota_store.list_overrides()  # type: ignore[attr-defined, no-any-return]

    def quota_set_override(
        self,
        token: str | None,
        user_id: str,
        downloads_per_day: int,
        valid_from: str | None = None,
        valid_until: str | None = None,
        note: str | None = None,
    ) -> None:
        self._require_admin(token)
        store = self._quota_store
        try:
            store.set_override(user_id, downloads_per_day, valid_from, valid_until, note)  # type: ignore[attr-defined]
        except TypeError:  # almacén en memoria sin `note`
            store.set_override(user_id, downloads_per_day, valid_from, valid_until)  # type: ignore[attr-defined]

    def quota_delete_override(self, token: str | None, user_id: str) -> None:
        self._require_admin(token)
        self._quota_store.delete_override(user_id)  # type: ignore[attr-defined]

    def revoke_donor_promotion(
        self, token: str | None, user_id: str, reason: str
    ) -> dict[str, object]:
        """Revoca el override donor vigente de un usuario (acción admin explícita).

        - Reutiliza el override existente (no hay sistema paralelo); lo elimina.
        - Idempotente: sin override vigente → `revoked=False` y **sin evento**.
        - Emite `promotion_reverted` (stage S3) con `reason` y el periodo revocado, para
          que el reconciliador NO resucite la promoción en ese mismo periodo.
        - No toca `download_quota_daily` ni `download_usage`.
        """
        self._require_admin(token)
        clean_reason = reason.strip() if isinstance(reason, str) else ""
        current: dict[str, object] | None = None
        for row in self._quota_store.list_overrides():  # type: ignore[attr-defined]
            if str(row.get("user_id")) == str(user_id):
                current = dict(row)
                break
        if current is None:
            return {"user_id": user_id, "revoked": False}
        valid_from = str(current.get("valid_from") or "")[:10] or None
        valid_until = str(current.get("valid_until") or "")[:10] or None
        self._quota_store.delete_override(user_id)  # type: ignore[attr-defined]
        # El histórico es responsabilidad separada: si falla, la revocación NO se deshace.
        self.record_funnel_event(
            "promotion_reverted",
            stage="S3",
            user_id=user_id,
            detail={"reason": clean_reason, "valid_from": valid_from, "valid_until": valid_until},
        )
        return {
            "user_id": user_id,
            "revoked": True,
            "reason": clean_reason,
            "valid_from": valid_from,
            "valid_until": valid_until,
        }

    def quota_usage(self, token: str | None, from_day: str, to_day: str) -> dict[str, object]:
        """Estadísticas de descargas (auditoría) en [from_day, to_day]; solo admin."""
        self._require_admin(token)
        return self._quota_store.usage_stats(from_day, to_day)  # type: ignore[attr-defined, no-any-return]
