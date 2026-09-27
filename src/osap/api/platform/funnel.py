"""PlatformApi: mixin de eventos del funnel (fase 4.2).

Registra los hitos del funnel en `funnel_events` (append-only) **sin tocar** el store de
cuota ni el circuito de descarga. La emisión concreta (limit_reached, registered, promociones)
se hace desde la capa que observa cada hecho (HTTP / reconciliador).
"""

from __future__ import annotations

import logging

from src.osap.api.platform.core import PlatformApiCore
from src.osap.infrastructure.state.funnel.memory import FunnelEvent, FunnelStage

_LOGGER = logging.getLogger("osap.funnel")


class FunnelMixin(PlatformApiCore):
    """Emite eventos del funnel de forma append-only y tolerante a fallos."""

    def record_funnel_event(
        self,
        event: object,
        *,
        stage: object | None = None,
        user_id: str | None = None,
        ip_address: str | None = None,
        override_id: int | None = None,
        detail: dict[str, object] | None = None,
        day: str | None = None,
    ) -> dict[str, object]:
        """Registra un evento del funnel. Un fallo al registrar no debe romper la petición."""
        try:
            return self._funnel_store.record_event(  # type: ignore[attr-defined, no-any-return]
                event if isinstance(event, FunnelEvent) else FunnelEvent(str(event)),
                stage=stage if isinstance(stage, FunnelStage) else (
                    FunnelStage(str(stage)) if stage is not None else None
                ),
                user_id=user_id,
                ip_address=ip_address,
                override_id=override_id,
                detail=detail,
                day=day,
            )
        except Exception as exc:  # noqa: BLE001 — la observación del funnel no es crítica
            _LOGGER.warning("no se pudo registrar el evento de funnel %s: %s", event, exc)
            return {}

    def record_funnel_event_once(
        self,
        event: object,
        *,
        user_id: str | None,
        stage: object | None = None,
        ip_address: str | None = None,
        override_id: int | None = None,
        detail: dict[str, object] | None = None,
        day: str | None = None,
    ) -> dict[str, object]:
        """Como `record_funnel_event` pero idempotente por `(user_id, event)`.

        Sirve para hitos que deben registrarse una sola vez por usuario (p. ej. `registered`)
        aunque la operación se reintente. Si el store falla, no interrumpe al llamante.
        """
        if not user_id:
            return self.record_funnel_event(
                event, stage=stage, user_id=user_id, ip_address=ip_address,
                override_id=override_id, detail=detail, day=day,
            )
        try:
            resolved = event if isinstance(event, FunnelEvent) else FunnelEvent(str(event))
            if self._funnel_store.has_event(user_id, resolved):  # type: ignore[attr-defined]
                return {}
        except Exception as exc:  # noqa: BLE001 — la guarda no debe romper el hito
            _LOGGER.warning("no se pudo comprobar el evento de funnel %s: %s", event, exc)
        return self.record_funnel_event(
            event, stage=stage, user_id=user_id, ip_address=ip_address,
            override_id=override_id, detail=detail, day=day,
        )
