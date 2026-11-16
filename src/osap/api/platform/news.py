"""Noticias musicales: acceso desde la sesión OSAP, sin buzón ni listas de usuarios.

La identidad y las preferencias viven en osap-auth. ai_noticias solo recibe idioma y
temas y devuelve el corpus. Este módulo no envía correo ni crea notificaciones.
"""

from __future__ import annotations

from src.osap.api.platform.core import PlatformApiCore
from src.osap.domain.votes import ForbiddenError, UnauthenticatedError

_LANGUAGES = {"es", "en", "fr", "de", "it", "pt", "ca"}


class NewsMixin(PlatformApiCore):
    def _news_identity(self, token: str | None) -> dict[str, object]:
        if not token:
            raise UnauthenticatedError("Login required")
        code, doc = self._container.auth_proxy().me(token)
        if code == 401:
            raise UnauthenticatedError("Login required")
        if code != 200 or not isinstance(doc, dict):
            raise ForbiddenError("No se pudo verificar la sesión")
        return doc

    def news_topics(self, token: str | None) -> dict[str, object]:
        self._news_identity(token)
        items = self._container.news_client().topics()
        return {"items": items, "count": len(items)}

    def news_feed(
        self,
        token: str | None,
        *,
        limit: int = 20,
        days: int = 30,
        topics: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> dict[str, object]:
        profile = self._news_identity(token)
        profile_language = str(profile.get("news_language") or "es").lower()
        raw_languages = profile.get("news_languages")
        profile_languages = (
            [str(item).strip().lower() for item in raw_languages if str(item).strip()]
            if isinstance(raw_languages, list)
            else []
        )
        selected_languages = [
            str(item).strip().lower()
            for item in (languages or profile_languages or [profile_language])
            if str(item).strip()
        ]
        selected_languages = [
            item for item in dict.fromkeys(selected_languages) if item in _LANGUAGES
        ] or ["es"]

        raw_topics = profile.get("news_topics")
        profile_topics = (
            [str(topic).strip() for topic in raw_topics if str(topic).strip()]
            if isinstance(raw_topics, list)
            else []
        )
        selected_topics = (
            [str(topic).strip() for topic in topics if str(topic).strip()]
            if topics is not None
            else profile_topics
        )

        data = self._container.news_client().query(
            languages=selected_languages,
            topics=selected_topics,
            limit=max(1, min(limit, 100)),
            days=max(1, min(days, 3650)),
        )
        items = data.get("items")
        return {
            "items": items if isinstance(items, list) else [],
            "language": selected_languages[0],
            "languages": selected_languages,
            "topics": selected_topics,
            "opt_in": bool(profile.get("news_opt_in")),
            "personalized": bool(selected_topics),
            "window_days": max(1, min(days, 3650)),
        }


