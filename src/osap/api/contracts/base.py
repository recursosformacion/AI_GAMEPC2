"""Contratos base (FastAPI DTO, F5.1): tipo frozen y re-exports de pydantic."""

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)
