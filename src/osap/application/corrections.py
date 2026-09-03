"""Circuito de soporte/correcciones del catálogo (OSAP).

Un único mecanismo parametrizado por `kind`:
- `contact`: mensaje general de contacto;
- `source` / `composer` / `work`: propuesta de corrección de datos de una entidad real
  del catálogo (identificada por `entity_id`; para obras OMR `entity_provider="omr"` y
  `field="title"`).

Las peticiones NO modifican el catálogo: se almacenan como `pending` para revisión
posterior (admin). Persistencia vía el store operativo de osap-api.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

VALID_KINDS = frozenset({"contact", "source", "composer", "work"})


class CorrectionError(Exception):
    """Error controlado de una solicitud de soporte (código HTTP + mensaje seguro)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class CorrectionService:
    """Valida y persiste solicitudes de contacto/corrección (siempre en estado pending)."""

    def __init__(
        self,
        store: Any,
        exists: Callable[[str, str], bool] | None = None,
    ) -> None:
        self._store = store
        self._exists = exists

    def submit(
        self,
        kind: str,
        message: str,
        entity_id: str | None = None,
        entity_provider: str | None = None,
        field: str | None = None,
        current_value: str | None = None,
        proposed_value: str | None = None,
        contact_email: str | None = None,
        requested_by: str | None = None,
    ) -> dict[str, object]:
        if kind not in VALID_KINDS:
            raise CorrectionError(422, "INVALID_KIND", "Tipo de solicitud no soportado")
        if not message or not message.strip():
            raise CorrectionError(422, "MESSAGE_REQUIRED", "El mensaje es obligatorio")
        if kind != "contact":
            if not entity_id or not str(entity_id).strip():
                raise CorrectionError(422, "ENTITY_REQUIRED", "La entidad es obligatoria")
            if kind == "work" and field == "title" and not entity_provider:
                entity_provider = "omr"
            if self._exists is not None and not self._exists(kind, str(entity_id)):
                raise CorrectionError(404, "ENTITY_NOT_FOUND", "La entidad indicada no existe")
        correction_id = f"corr-{uuid.uuid4().hex[:10]}"
        row: dict[str, object] = self._store.add_correction(
            correction_id,
            kind,
            entity_id,
            entity_provider,
            field,
            current_value,
            proposed_value,
            message,
            contact_email,
            requested_by,
        )
        return row
