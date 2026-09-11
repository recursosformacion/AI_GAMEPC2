"""Almacén de sesiones de resolución de osap-api (OpStore).

Misma base de datos operativa que `op_store` (MySQL con fallback a memoria), pero para el
modelo de resolución del ADR-0033 / resolution-store-v1: `resolution_sessions`,
`provider_results` y `resolution_items`. Contiene SOLO estado operativo de una operación
de resolución concreta; nunca una copia del catálogo de osap-storage.

Facade (F5.8): la implementación vive en `src/osap/infrastructure/state/resolution/`.
"""

from __future__ import annotations

from src.osap.infrastructure.state.resolution import (
    _item_same,
    _j,
    _json_eq,
    _MemoryStore,
    _MysqlStore,
    _now,
    build_resolution_store,
)

__all__ = [
    "build_resolution_store",
    "_MemoryStore",
    "_MysqlStore",
    "_now",
    "_j",
    "_item_same",
    "_json_eq",
]
