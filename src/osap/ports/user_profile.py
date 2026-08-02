from abc import ABC, abstractmethod

from ..domain.user_profile import UserProfile


class IUserProfileStore(ABC):
    """Stores user preferences used by the RankingEngine."""

    @abstractmethod
    def get(self, user_id: str) -> UserProfile | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, profile: UserProfile) -> None:
        raise NotImplementedError
