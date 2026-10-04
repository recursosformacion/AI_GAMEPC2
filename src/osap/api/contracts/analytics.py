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


class ActivityMeSummary(_Frozen):
    downloads: int = 0
    bytes: int = 0
    contributions_total: int = 0
    contributions_accepted: int = 0
    contributions_pending: int = 0
    works: int = 0


class ActivityMeResponse(_Frozen):
    """Panel personal «Mi Actividad» (`/api/v1/activity/me`).

    Compone datos ya existentes del propio usuario: cuota/descargas, aportaciones, pendientes,
    descargas detalladas, impacto y actividad reciente. No expone datos de otros usuarios.
    """

    user_id: str
    period: AnalyticsMePeriod
    access: AnalyticsMeAccess
    quota: AnalyticsMeQuota
    summary: ActivityMeSummary
    my_downloads: list[dict[str, object]] = Field(default_factory=list)
    my_contributions: list[dict[str, object]] = Field(default_factory=list)
    pending: list[dict[str, object]] = Field(default_factory=list)
    impact: dict[str, object] = Field(default_factory=dict)
    recent: list[dict[str, object]] = Field(default_factory=list)


class FunnelMetricsPeriod(_Frozen):
    from_day: str
    to_day: str


class FunnelEventCounts(_Frozen):
    anon_limit_reached: int = 0
    registered: int = 0
    user_limit_reached: int = 0
    membership_activated: int = 0
    membership_lapsed: int = 0
    promotion_applied: int = 0
    promotion_reverted: int = 0


class FunnelConversions(_Frozen):
    anon_to_user: int = 0
    user_to_donor: int = 0


class FunnelDownloadProvider(_Frozen):
    provider: str
    total: int = 0


class FunnelDownloads(_Frozen):
    total: int = 0
    anonymous: int = 0
    registered: int = 0
    by_provider: list[FunnelDownloadProvider] = Field(default_factory=list)


class FunnelMetricsResponse(_Frozen):
    """Métricas del funnel S0–S4 (`/api/v1/admin/analytics/funnel`).

    Derivadas exclusivamente de `funnel_events` + `download_usage` (sin contadores ni tablas
    nuevas). `events` cuenta operaciones; `users`, usuarios únicos.
    """

    period: FunnelMetricsPeriod
    events: FunnelEventCounts
    users: FunnelEventCounts
    conversions: FunnelConversions
    downloads: FunnelDownloads
