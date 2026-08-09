"""V1 — Store de votos en memoria (tests / entornos sin osap-storage).

Implementa :class:`IVoteStore` con la misma semántica que Storage (regla
``UNIQUE(user_id, work_id, vote_day)`` → ``DuplicateVoteError``) para poder probar el
orquestador de osap-api sin red ni BD propia.
"""

from datetime import UTC, datetime

from src.osap.domain.votes import ComposerStats, DuplicateVoteError, WorkStats, WorkVote
from src.osap.ports.votes import IVoteStore


class MemoryVoteStore(IVoteStore):
    """Implementación en memoria de :class:`IVoteStore` (solo tests/dev)."""

    def __init__(self) -> None:
        self._votes: list[WorkVote] = []
        self._work_stats: dict[str, WorkStats] = {}
        self._composer_stats: dict[str, ComposerStats] = {}
        self._execution: dict[str, object] | None = None

    def insert_vote(self, vote: WorkVote) -> WorkVote:
        for existing in self._votes:
            if (
                existing.user_id is not None
                and existing.user_id == vote.user_id
                and existing.work_id == vote.work_id
                and existing.vote_day == vote.vote_day
            ):
                raise DuplicateVoteError("Already voted for this work today")
        self._votes.append(vote)
        self._refresh(vote.work_id, vote.composer_id)
        return vote

    def _refresh(self, work_id: str, composer_id: str | None) -> None:
        work_votes = [v for v in self._votes if v.work_id == work_id]
        count = len(work_votes)
        total = sum(v.vote for v in work_votes)
        avg = round(total / count, 2) if count else None
        self._work_stats[work_id] = WorkStats(
            work_id=work_id, vote_count=count, vote_sum=total, vote_average=avg, updated_at=datetime.now(UTC)
        )
        if composer_id:
            composer_votes = [v for v in self._votes if v.composer_id == composer_id]
            ccount = len(composer_votes)
            ctotal = sum(v.vote for v in composer_votes)
            cavg = round(ctotal / ccount, 2) if ccount else None
            self._composer_stats[composer_id] = ComposerStats(
                composer_id=composer_id,
                vote_count=ccount,
                vote_sum=ctotal,
                vote_average=cavg,
                updated_at=datetime.now(UTC),
            )

    def work_statistics(self, work_id: str) -> WorkStats | None:
        return self._work_stats.get(work_id)

    def composer_statistics(self, composer_id: str) -> ComposerStats | None:
        return self._composer_stats.get(composer_id)

    def anonymize_user(self, user_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        work_ids: set[str] = set()
        composer_ids: set[str] = set()
        for vote in self._votes:
            if vote.user_id == user_id:
                work_ids.add(vote.work_id)
                if vote.composer_id:
                    composer_ids.add(vote.composer_id)
                self._votes[self._votes.index(vote)] = WorkVote(
                    vote=vote.vote,
                    work_id=vote.work_id,
                    user_id=None,
                    composer_id=vote.composer_id,
                    id=vote.id,
                    voted_at=vote.voted_at,
                    vote_day=vote.vote_day,
                    anonymized=True,
                )
        for work_id in work_ids:
            composer = next((v.composer_id for v in self._votes if v.work_id == work_id), None)
            self._refresh(work_id, composer)
        return tuple(work_ids), tuple(composer_ids)

    def total_votes(self) -> int:
        return len(self._votes)

    def top_works(self, limit: int = 20) -> list[WorkStats]:
        return sorted(
            self._work_stats.values(), key=lambda s: (s.vote_average or 0, s.vote_count), reverse=True
        )[:limit]

    def top_composers(self, limit: int = 20) -> list[ComposerStats]:
        return sorted(
            self._composer_stats.values(), key=lambda s: (s.vote_average or 0, s.vote_count), reverse=True
        )[:limit]

    def last_execution(self) -> dict[str, object] | None:
        return self._execution
