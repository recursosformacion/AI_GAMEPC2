"""Contratos de la atribución asistida por IA (revisión humana de propuestas).

La SPA no contiene lógica de IA: consume los endpoints de osap-api, que delega en
osap-storage. El contrato de respuesta es el documento de la propuesta tal cual lo devuelve
storage (`dict`) para no duplicar aquí su esquema.

`reviewed_by` NO viaja en la petición: se deriva del `UserPrincipal` autenticado, de modo que
nadie puede atribuir una revisión a otro usuario.
"""

from .base import _Frozen


class WorkAiReviewRequest(_Frozen):
    """Acción de revisión humana sobre una propuesta de atribución."""

    action: str
    note: str | None = None
