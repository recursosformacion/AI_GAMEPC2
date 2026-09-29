"""Analítica de uso (solo lectura, admin).

Separada de `work_statistics` (valoración por votos, en osap-storage): aquí se exponen
contadores de utilización de OSAP y de las fuentes.
"""

from pydantic import ConfigDict, Field

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


class AnalyticsMeProvider(_Frozen):
    provider: str
    downloads: int = 0
    bytes: int = 0


class AnalyticsMePeriod(_Frozen):
    from_day: str
    to_day: str


class AnalyticsMeAccess(_Frozen):
    stage: str
    tier: str


class AnalyticsMeQuota(_Frozen):
    limit: int = 0
    used: int = 0
    remaining: int = 0


class AnalyticsMeDownloads(_Frozen):
    count: int = 0
    bytes: int = 0
    providers: list[AnalyticsMeProvider] = Field(default_factory=list)


class AnalyticsMeResponse(_Frozen):
    """Estadísticas del propio usuario (`/api/v1/analytics/me`).

    Solo agregados filtrados por el `user_id` del token: actividad/descargas, cuota y etapa
    del funnel. No expone datos de otros usuarios ni parámetros de identidad.
    """

    period: AnalyticsMePeriod
    access: AnalyticsMeAccess
    quota: AnalyticsMeQuota
    downloads: AnalyticsMeDownloads
