"""V1 — Puertos para votos, estadísticas y autenticación.

Fronteras de contrato: la persistencia de votos y estadísticas se delega en
**osap-storage** vía ``IVoteStore`` (nunca en la BD de osap-api). La identidad de
usuario (``IAuthenticator``) se resuelve desde el access token; la identidad de
Work/compositor (``IWorkStore``) usa el contrato de Storage.
"""

from abc import ABC, abstractmethod

from src.osap.domain.votes import ComposerStats, WorkStats, WorkVote


class IAuthenticator(ABC):
    """Resuelve el ``user_id`` (UUID) a partir de un access token válido."""

    @abstractmethod
    def user_id_for(self, token: str | None) -> str | None:
        raise NotImplementedError


class IWorkStore(ABC):
    """Identidad de Work vía el contrato de Storage (nunca su BD).

    Devuelve el ``composer_id`` de una Work, o ``None`` si la Work no existe.
    """

    @abstractmethod
    def composer_id_for(self, work_id: str) -> str | None:
        raise NotImplementedError


class IVoteStore(ABC):
    """Persistencia de votos y estadísticas agregadas en osap-storage.

    La regla ``UNIQUE(user_id, work_id, vote_day)`` se impone en Storage; un conflicto
    se traduce en ``DuplicateVoteError`` (HTTP 409).
    """

    @abstractmethod
    def insert_vote(self, vote: WorkVote) -> WorkVote:
        raise NotImplementedError

    @abstractmethod
    def work_statistics(self, work_id: str) -> WorkStats | None:
        raise NotImplementedError

    @abstractmethod
    def composer_statistics(self, composer_id: str) -> ComposerStats | None:
        raise NotImplementedError

    @abstractmethod
    def anonymize_user(self, user_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Anonimiza los votos de un usuario. Devuelve (work_ids, composer_ids) afectados."""
        raise NotImplementedError

    @abstractmethod
    def total_votes(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def top_works(self, limit: int = 20) -> list[WorkStats]:
        raise NotImplementedError

    @abstractmethod
    def top_composers(self, limit: int = 20) -> list[ComposerStats]:
        raise NotImplementedError

    @abstractmethod
    def last_execution(self) -> dict[str, object] | None:
        raise NotImplementedError
