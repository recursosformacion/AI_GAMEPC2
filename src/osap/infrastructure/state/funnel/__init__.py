"""Eventos del funnel de acceso y contribución (fase 4.2). Append-only."""

from .factory import build_funnel_store
from .memory import FunnelEvent, FunnelStage, MemoryStore, today

__all__ = ["FunnelEvent", "FunnelStage", "MemoryStore", "build_funnel_store", "today"]
