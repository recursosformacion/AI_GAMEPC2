"""Resolución de adquisición de una representación.

OSAP ya sabe encontrar obras y representaciones. Esta capa decide CÓMO puede
obtenerse cada representación, sin descargar nada todavía (la descarga será la
V2, un DownloadManager que consumirá esta información).

Estados de adquisición:

  LOCAL      el fichero existe en el repositorio local y puede abrirse directo.
  DIRECT     existe una URL de descarga directa (mirror propio, web, Drive...).
  EXTERNAL   OSAP solo conoce la página del proveedor (ej. IMSLP); no scrapea,
             la aplicación entrega la URL para descarga manual del cliente.
  MANUAL     el proveedor no ofrece descarga individual (ej. PDMX sin mirror);
             OSAP informa del motivo.
  UNAVAILABLE no existe forma conocida de obtener el recurso.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.osap.domain.candidate_representation import CandidateRepresentation


class AcquisitionMethod(StrEnum):
    LOCAL = "LOCAL"
    DIRECT = "DIRECT"
    EXTERNAL = "EXTERNAL"
    MANUAL = "MANUAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class AcquisitionInfo:
    """Cómo adquirir una representación (para consumo del futuro DownloadManager)."""

    provider: str
    format: str
    method: AcquisitionMethod
    url: str | None = None
    local_path: str | None = None
    reason: str | None = None


class AcquisitionResolver:
    """Clasifica cada representación en su método de adquisición."""

    def resolve(self, rep: CandidateRepresentation) -> AcquisitionInfo:
        provider = rep.provider_id.value
        fmt = rep.format.value

        # 1. LOCAL: fichero presente en el repositorio local.
        local_path = rep.local_path
        if local_path and Path(local_path).exists():
            return AcquisitionInfo(provider, fmt, AcquisitionMethod.LOCAL, local_path=local_path)

        # 2. DIRECT: descarga directa disponible (mirror/web/Drive).
        if rep.downloadable and not rep.manual_download:
            return AcquisitionInfo(provider, fmt, AcquisitionMethod.DIRECT, url=rep.download_url)

        # 3. EXTERNAL: solo se conoce la página del proveedor (descarga manual del cliente).
        if rep.manual_download or (rep.download_url and rep.download_url.startswith(("http://", "https://"))):
            return AcquisitionInfo(
                provider,
                fmt,
                AcquisitionMethod.EXTERNAL,
                url=rep.download_url,
                reason=rep.notes,
            )

        # 4. MANUAL: sin descarga individual, se informa del motivo.
        reason = str(rep.metadata.get("acquisition_reason") or "") or rep.notes
        if reason:
            return AcquisitionInfo(provider, fmt, AcquisitionMethod.MANUAL, reason=reason)

        # 5. UNAVAILABLE.
        return AcquisitionInfo(provider, fmt, AcquisitionMethod.UNAVAILABLE, reason="Sin forma de obtener el recurso")
