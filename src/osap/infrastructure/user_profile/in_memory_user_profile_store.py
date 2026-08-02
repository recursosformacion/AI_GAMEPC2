from src.osap.domain.user_profile import UserProfile
from src.osap.ports.user_profile import IUserProfileStore


class InMemoryUserProfileStore(IUserProfileStore):
    def __init__(self) -> None:
        self._profiles: dict[str, UserProfile] = {}

    def get(self, user_id: str) -> UserProfile | None:
        return self._profiles.get(user_id)

    def save(self, profile: UserProfile) -> None:
        self._profiles[profile.user_id] = profile
