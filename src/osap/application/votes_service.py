"""V1 — Servicio de votos y estadísticas (application layer).

Orquesta: validación de la escala 1..5, resolución de identidad de Work vía Storage,
y delegación de la persistencia/agregación a **osap-storage** (``IVoteStore``). No
resuelve compositores, usuarios ni normaliza nada: eso pertenece a Storage / Auth.
"""

from src.osap.domain.principal import Principal, UserPrincipal
from src.osap.domain.votes import (
    MAX_VOTE,
    MIN_VOTE,
    ComposerStats,
    DuplicateVoteError,
    ForbiddenError,
    InvalidVoteError,
    UnauthenticatedError,
    WorkNotFoundError,
    WorkStats,
    WorkVote,
    utc_now,
)
from src.osap.ports.votes import IAuthenticator, IVoteStore, IWorkStore


class VotesService:
    """Casos de uso de votación y estadísticas (los votos viven en osap-storage)."""

    def __init__(
        self,
        votes: IVoteStore,
        works: IWorkStore,
        authenticator: IAuthenticator,
    ) -> None:
        self._votes = votes
        self._works = works
        self._authenticator = authenticator

    # -- autenticación / autorización ----------------------------------------

    def principal_for(self, token: str | None) -> Principal | None:
        return self._authenticator.resolve(token)

    def require_user(self, token: str | None) -> UserPrincipal:
        principal = self._authenticator.resolve(token)
        if not isinstance(principal, UserPrincipal):
            raise UnauthenticatedError("Missing or invalid access token")
        return principal

    def require_can_vote(self, token: str | None) -> UserPrincipal:
        user = self.require_user(token)
        if not user.email_verified or not user.has_role("user"):
            raise ForbiddenError("A verified user role is required to vote")
        return user

    def require_admin(self, token: str | None) -> UserPrincipal:
        user = self.require_user(token)
        if not user.has_role("admin"):
            raise ForbiddenError("Admin role required")
        return user

    # -- votación ------------------------------------------------------------

    def cast_vote(self, token: str | None, work_id: str, vote: int) -> WorkVote:
        user = self.require_can_vote(token)
        if not isinstance(vote, int) or isinstance(vote, bool) or not (MIN_VOTE <= vote <= MAX_VOTE):
            raise InvalidVoteError(f"Vote must be between {MIN_VOTE} and {MAX_VOTE}")

        composer_id = self._works.composer_id_for(work_id)
        if composer_id is None:
            raise WorkNotFoundError("Work not found")

        voted_at = utc_now()
        new_vote = WorkVote(
            vote=vote,
            work_id=work_id,
            user_id=user.user_id,
            composer_id=composer_id,
            voted_at=voted_at,
        )
        try:
            return self._votes.insert_vote(new_vote)
        except DuplicateVoteError:
            raise

    # -- estadísticas --------------------------------------------------------

    def work_statistics(self, work_id: str) -> WorkStats:
        stats = self._votes.work_statistics(work_id)
        if stats is not None:
            return stats
        return WorkStats(work_id=work_id, vote_count=0, rating=None)

    def composer_statistics(self, composer_id: str) -> ComposerStats:
        stats = self._votes.composer_statistics(composer_id)
        if stats is not None:
            return stats
        return ComposerStats(composer_id=composer_id, vote_count=0, rating=None)

    # -- user.deleted --------------------------------------------------------

    def handle_user_deleted(self, user_id: str) -> dict[str, object]:
        """Pide a Storage que anonimice los votos del usuario (conserva el agregado)."""
        work_ids, composer_ids = self._votes.anonymize_user(user_id)
        return {"anonymized_works": len(work_ids), "anonymized_composers": len(composer_ids)}

    # -- admin ---------------------------------------------------------------

    def overview(self, top: int = 20) -> dict[str, object]:
        return {
            "total_votes": self._votes.total_votes(),
            "top_works": [_work_stats_to_dict(s) for s in self._votes.top_works(top)],
            "top_composers": [_composer_stats_to_dict(s) for s in self._votes.top_composers(top)],
            "last_execution": self._votes.last_execution(),
        }


def _work_stats_to_dict(stats: WorkStats) -> dict[str, object]:
    return {
        "work_id": stats.work_id,
        "vote_count": stats.vote_count,
        "rating": stats.rating,
        "work_count": stats.work_count,
    }


def _composer_stats_to_dict(stats: ComposerStats) -> dict[str, object]:
    return {
        "composer_id": stats.composer_id,
        "vote_count": stats.vote_count,
        "rating": stats.rating,
        "work_count": stats.work_count,
    }
