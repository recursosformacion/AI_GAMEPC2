"""PlatformApi: mixin de lectura para la capa pública SEO (compositor y obra).

No expone endpoints JSON: alimenta el router HTML (`api/http/seo.py`). Reutiliza el índice
local para las obras (rápido y determinista) y osap-storage para la ficha/biografía de la
persona, igual que el resto de la API pública.
"""

from __future__ import annotations

from typing import cast

from src.osap.api.platform.core import PlatformApiCore
from src.osap.infrastructure.storage.storage_composer_client import StorageComposerError


class SeoMixin(PlatformApiCore):
    def seo_work(self, work_id: str) -> dict[str, object] | None:
        """Ficha de obra del índice local (None si no existe o el índice no responde)."""
        provider = self._index_provider()
        if provider is None:
            return None
        getter = getattr(provider, "get_work_with_representations", None)
        if not callable(getter):
            return None
        return cast("dict[str, object] | None", getter(work_id))

    def seo_person(self, person_id: str) -> dict[str, object] | None:
        """Ficha pública de una persona (con biografía). None si no es visible o falla."""
        try:
            detail = self.composers().get_composer_biography(person_id)
        except StorageComposerError:
            return None
        if detail is None or not bool(detail.get("visible", True)):
            return None
        return detail

    def seo_person_works(self, person_id: str, limit: int, offset: int) -> dict[str, object]:
        """Obras de una persona: índice local y, si no tiene, fallback a osap-storage."""
        provider = self._index_provider()
        if provider is not None:
            lister = getattr(provider, "list_works_by_person", None)
            if callable(lister):
                data = lister(person_id, limit, offset)
                if isinstance(data, dict) and data.get("items"):
                    return cast("dict[str, object]", data)
        try:
            return self.composers().composer_works(person_id, limit, offset)
        except StorageComposerError:
            return {"items": [], "total": 0}

    def _index_provider(self) -> object | None:
        """Proveedor `index` del catálogo, o None si no está registrado/accesible."""
        try:
            for provider in self._container.catalog_manager().providers():
                if provider.provider_id.value == "index":
                    return provider
        except Exception:  # noqa: BLE001 — la capa SEO nunca debe tumbar la app
            return None
        return None
