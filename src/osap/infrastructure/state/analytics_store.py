"""Analítica de uso de osap-api (MySQL operativo, con degradación a memoria).

Aloja SOLO contadores de uso: agregados diarios de búsquedas, descargas
(dimensión usuario+proveedor+día) y agregados por proveedor. No guarda el historial de
búsquedas por usuario y no se mezcla con `work_statistics` (valoración, en osap-storage).

Facade: la implementación vive en `src/osap/infrastructure/state/analytics/`.
Diseño: `docs/osap/usage-analytics-design.md`.
"""

from __future__ import annotations

from src.osap.infrastructure.state.analytics import (
    ANON_USER,
    AnalyticsRecorder,
    _MemoryStore,
    _MysqlStore,
    _today,
    build_analytics_store,
)

__all__ = [
    "ANON_USER",
    "AnalyticsRecorder",
    "build_analytics_store",
    "_MemoryStore",
    "_MysqlStore",
    "_today",
]
