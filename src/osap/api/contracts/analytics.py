"""Analítica de uso (solo lectura, admin).

Separada de `work_statistics` (valoración por votos, en osap-storage): aquí se exponen
contadores de utilización de OSAP y de las fuentes.
"""

from pydantic import ConfigDict

from .base import _Frozen


class AnalyticsOverviewResponse(_Frozen):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "from_day": "2026-09-01",
                    "to_day": "2026-09-12",
                    "searches_total": 120,
                    "searches_with_results": 95,
                    "searches_without_results": 25,
                    "downloads_total": 40,
                    "downloads_bytes": 10485760,
                    "downloads_users": 7,
                }
            ]
        },
    )
    from_day: str
    to_day: str
    searches_total: int = 0
    searches_with_results: int = 0
    searches_without_results: int = 0
    downloads_total: int = 0
    downloads_bytes: int = 0
    downloads_users: int = 0
