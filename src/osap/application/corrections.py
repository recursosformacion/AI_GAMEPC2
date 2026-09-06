"""Circuito de soporte/correcciones del catálogo (OSAP).

Un único mecanismo parametrizado por `kind`:
- `contact`: mensaje general de contacto (público, sin entidad);
- `source` / `composer` / `work`: propuesta de corrección de datos de una entidad real
  del catálogo (identificada por `entity_id`). Solo se admiten los `field` de
  `ALLOWED_FIELDS` (campos que OSAP puede revisar). Para obras solo se permite el
  TÍTULO de obras de OSAP-storage (OMR): el backend fija `entity_provider="omr"` y no
  es una combinación que el cliente pueda elegir.

Las peticiones NO modifican el catálogo: se almacenan como `pending` para revisión
posterior (admin). Persistencia vía el store operativo de osap-api.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

VALID_KINDS = frozenset({"contact", "source", "composer", "work"})

# Campos que OSAP puede realmente revisar/modificar por tipo de entidad. Fuera de esta
# lista no se acepta ninguna propuesta (evita prometer correcciones imposibles).
ALLOWED_FIELDS: dict[str, frozenset[str]] = {
    "source": frozenset({"name", "description", "url"}),
    "composer": frozenset({"name", "aliases", "biography", "birth_year", "death_year"}),
    "work": frozenset({"title"}),
}

# La única corrección de obra admitida es el título de una obra de OSAP-storage (OMR).
WORK_ALLOWED_PROVIDER = "omr"


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
        requested_by_name: str | None = None,
        requested_by_email: str | None = None,
    ) -> dict[str, object]:
        if kind not in VALID_KINDS:
            raise CorrectionError(422, "INVALID_KIND", "Tipo de solicitud no soportado")
        if not message or not message.strip():
            raise CorrectionError(422, "MESSAGE_REQUIRED", "El mensaje es obligatorio")
        if kind == "contact":
            if entity_id or entity_provider or field:
                raise CorrectionError(
                    422, "CONTACT_NO_ENTITY", "El contacto general no identifica una entidad"
                )
            row: dict[str, object] = self._store.add_correction(
                f"corr-{uuid.uuid4().hex[:10]}",
                kind,
                None,
                None,
                None,
                None,
                None,
                message,
                contact_email,
                requested_by,
                requested_by_name,
                requested_by_email,
            )
            return row

        # --- Correcciones de datos (source | composer | work) -----------------
        if not entity_id or not str(entity_id).strip():
            raise CorrectionError(422, "ENTITY_REQUIRED", "La entidad es obligatoria")
        if field and field not in ALLOWED_FIELDS.get(kind, frozenset()):
            raise CorrectionError(
                422, "FIELD_NOT_ALLOWED", "Este campo no puede proponerse para ese tipo de entidad"
            )
        if kind == "work":
            # Solo se admite la corrección del TÍTULO de obras OSAP-storage (OMR). El
            # proveedor lo fija el backend: el cliente no puede elegir otro origen.
            if field not in (None, "title"):
                raise CorrectionError(422, "FIELD_NOT_ALLOWED", "Solo se admite corregir el título de la obra")
            field = "title"
            entity_provider = WORK_ALLOWED_PROVIDER
        # field / proposed_value son metadatos opcionales: el detalle de la corrección
        # puede describirse libremente en `message` (texto plano del usuario).
        if self._exists is not None and not self._exists(kind, str(entity_id)):
            raise CorrectionError(404, "ENTITY_NOT_FOUND", "La entidad indicada no existe")
        correction_id = f"corr-{uuid.uuid4().hex[:10]}"
        created: dict[str, object] = self._store.add_correction(
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
            requested_by_name,
            requested_by_email,
        )
        return created
