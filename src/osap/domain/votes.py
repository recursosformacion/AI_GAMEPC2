"""V1 — Votos de obras y estadísticas agregadas (dominio).

Modelo persistente de votación (1..5) con la regla: un usuario puede valorar una obra
como máximo una vez al día (UTC). Las estadísticas agregadas de obras y de compositores
se calculan siempre a partir de los votos originales, nunca como media de medias.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

MIN_VOTE = 1
MAX_VOTE = 5


class InvalidVoteError(ValueError):
    """Vote fuera de la escala 1..5."""


class WorkNotFoundError(Exception):
    """La Work no existe (según el contrato de Storage)."""


class DuplicateVoteError(Exception):
    """El usuario ya votó esta Work durante el mismo día."""


class UnauthenticatedError(Exception):
    """No se pudo autenticar la identidad del usuario."""


def _validate_vote(vote: int) -> int:
    if isinstance(vote, bool) or not isinstance(vote, int) or not (MIN_VOTE <= vote <= MAX_VOTE):
        raise InvalidVoteError(f"Vote must be between {MIN_VOTE} and {MAX_VOTE}")
    return vote


@dataclass(frozen=True)
class WorkVote:
    """Un voto de un usuario a una obra.

    ``user_id`` es opaco (UUID) y puede ser ``None`` cuando el voto ha sido anonimizado
    tras el evento ``user.deleted``. Nunca guarda PII. ``composer_id`` se denormaliza aquí
    (obtenido del contrato de Storage) para poder agregar estadísticas de compositor.
    """

    vote: int
    work_id: str
    user_id: str | None
    composer_id: str | None = None
    id: str = ""
    voted_at: datetime | None = None
    vote_day: str | None = None
    anonymized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "vote", _validate_vote(self.vote))
        if not self.id:
            object.__setattr__(self, "id", uuid4().hex)
        voted_at = self.voted_at if self.voted_at is not None else utc_now()
        object.__setattr__(self, "voted_at", voted_at)
        if self.vote_day is None:
            object.__setattr__(self, "vote_day", _utc_date(voted_at))


def _utc_date(dt: datetime) -> str:
    return dt.date().isoformat()


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class VoteStats:
    """Agregado estadístico (peso real, no media de medias)."""

    vote_count: int
    vote_sum: int
    vote_average: float | None

    @classmethod
    def from_votes(cls, votes: list["WorkVote"]) -> "VoteStats":
        count = len(votes)
        total = sum(v.vote for v in votes)
        average = round(total / count, 2) if count else None
        return cls(vote_count=count, vote_sum=total, vote_average=average)


@dataclass(frozen=True)
class WorkStats:
    work_id: str
    vote_count: int
    vote_sum: int
    vote_average: float | None
    updated_at: datetime | None = field(default=None)


@dataclass(frozen=True)
class ComposerStats:
    composer_id: str
    vote_count: int
    vote_sum: int
    vote_average: float | None
    updated_at: datetime | None = field(default=None)
