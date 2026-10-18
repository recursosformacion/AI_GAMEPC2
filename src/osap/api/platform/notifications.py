"""Notificaciones de la app (campana): bandeja por usuario + avisos globales.

Un aviso global (`user_id IS NULL`) solo se muestra a administradores; los personales
(`user_id`) a su destinatario. El estado leído es del aviso (global = para todos los admins).
"""

from __future__ import annotations

from src.osap.api.platform.core import PlatformApiCore
from src.osap.domain.principal import UserPrincipal


class NotificationsMixin(PlatformApiCore):
    def _notifications_scope(self, token: str | None) -> tuple[str, bool] | None:
        principal = self.current_user(token)
        if not isinstance(principal, UserPrincipal):
            return None
        return principal.user_id, principal.has_role("admin")

    def list_notifications(self, token: str | None, limit: int = 50) -> dict[str, object] | None:
        scope = self._notifications_scope(token)
        if scope is None:
            return None
        user_id, is_admin = scope
        bounded = max(1, min(limit, 100))
        items = self._store.list_notifications(
            user_id=user_id, include_global=is_admin, limit=bounded
        )
        unread = self._store.count_unread_notifications(
            user_id=user_id, include_global=is_admin
        )
        return {"items": items, "unread": unread}

    def count_unread_notifications(self, token: str | None) -> int | None:
        scope = self._notifications_scope(token)
        if scope is None:
            return None
        user_id, is_admin = scope
        return self._store.count_unread_notifications(
            user_id=user_id, include_global=is_admin
        )

    def mark_notification_read(self, token: str | None, notification_id: int) -> bool | None:
        scope = self._notifications_scope(token)
        if scope is None:
            return None
        user_id, _ = scope
        return self._store.mark_notification_read(
            notification_id=notification_id, user_id=user_id
        )

    def mark_all_notifications_read(self, token: str | None) -> bool | None:
        scope = self._notifications_scope(token)
        if scope is None:
            return None
        user_id, is_admin = scope
        return self._store.mark_all_notifications_read(
            user_id=user_id, include_global=is_admin
        )
