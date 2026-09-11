"""Votos y estadísticas."""

from pydantic import ConfigDict

from .base import _Frozen


class VerifyEmailRequest(_Frozen):
    token: str


# --- votes & statistics (v1) -----------------------------------------------


class VoteRequest(_Frozen):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={"examples": [{"vote": 5}]},
    )
    vote: int


class VoteResponse(_Frozen):
    work_id: str
    vote: int
    voted_at: str
    vote_day: str


class WorkStatisticsResponse(_Frozen):
    work_id: str
    rating: float | None
    adjusted_rating: float | None = None
    vote_count: int = 0
    work_count: int = 1
    confidence: float | None = None
    calculated_at: str | None = None


class ComposerStatisticsResponse(_Frozen):
    composer_id: str
    rating: float | None
    adjusted_rating: float | None = None
    vote_count: int = 0
    work_count: int = 0
    confidence: float | None = None
    calculated_at: str | None = None


class VotesOverviewResponse(_Frozen):
    total_votes: int
    top_works: list[WorkStatisticsResponse] = []
    top_composers: list[ComposerStatisticsResponse] = []
    last_execution: dict[str, object] | None = None


# --- compositores (consulta pública + fusión admin) --------------------------


