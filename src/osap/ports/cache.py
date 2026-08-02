from abc import ABC, abstractmethod


class ICache(ABC):
    """Cache with TTL and versioning to avoid re-downloading resources."""

    @abstractmethod
    def get(self, key: str) -> object | None:
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: object, ttl_seconds: int | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def invalidate(self, key: str) -> None:
        raise NotImplementedError
