"""PlatformApi: mixin de analítica de uso (estadísticas de uso y proveedores)."""

from __future__ import annotations

import logging

from src.osap.api.platform.core import PlatformApiCore

_LOGGER = logging.getLogger("osap.analytics")

VERSION = "3.1"


class AnalyticsMixin(PlatformApiCore):
    """Registro no bloqueante de eventos de uso y consulta agregada (admin)."""

    def record_search_event(self, result_total: int) -> None:
        """Cuenta una búsqueda completada (una por llamada; el cache hit también cuenta)."""
        try:
            self._analytics.record_search(result_total)
        except Exception:  # noqa: BLE001 — la analítica nunca rompe la petición
            _LOGGER.warning("No se pudo registrar la búsqueda", exc_info=True)

    def record_download_event(
        self,
        *,
        provider: str,
        work_id: str,
        fmt: str,
        user_id: str | None = None,
        bytes_transferred: int = 0,
    ) -> None:
        """Cuenta una solicitud de descarga iniciada desde OSAP (con usuario y proveedor)."""
        try:
            self._analytics.record_download(
                provider=provider,
                work_id=work_id,
                fmt=fmt,
                user_id=user_id,
                bytes_transferred=bytes_transferred,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning("No se pudo registrar la descarga", exc_info=True)

    def record_download_failure_event(self, *, provider: str) -> None:
        """Cuenta una descarga fallida (upstream no sirvió el fichero)."""
        try:
            self._analytics.record_download_failure(provider)
        except Exception:  # noqa: BLE001
            _LOGGER.warning("No se pudo registrar el fallo de descarga", exc_info=True)

    def analytics_overview(self, from_day: str, to_day: str) -> dict[str, int]:
        """Vuelca el buffer y devuelve los agregados del rango [from_day, to_day]."""
        try:
            self._analytics.flush()
        except Exception:  # noqa: BLE001 — leer no debe fallar por un flush
            _LOGGER.warning("No se pudo volcar la analítica antes de leer", exc_info=True)
        return self._analytics_store.usage_overview(from_day, to_day)
