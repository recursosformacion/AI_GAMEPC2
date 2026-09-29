"""Contratos de la atribución asistida por IA (revisión humana de propuestas).

La SPA no contiene lógica de IA: consume los endpoints de osap-api, que delega en
osap-storage. El contrato de respuesta es el documento de la propuesta tal cual lo devuelve
storage (`dict`) para no duplicar aquí su esquema.
"""

from .base import _Frozen


class WorkAiReviewRequest(_Frozen):
    """Acción de revisión humana sobre una propuesta de atribución."""

    action: str
    note: str | None = None
    reviewed_by: str | None = None
