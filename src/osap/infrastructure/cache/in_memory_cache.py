import time

from src.osap.ports.cache import ICache


class _Entry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: object, ttl_seconds: int | None) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl_seconds if ttl_seconds is not None else None


class InMemoryCache(ICache):
    """TTL cache with a version suffix to avoid stale resources."""

    def __init__(self, version: str = "v1") -> None:
        self._data: dict[str, _Entry] = {}
        self._version = version

    def get(self, key: str) -> object | None:
        entry = self._data.get(self._key(key))
        if entry is None:
            return None
        if entry.expires_at is not None and time.monotonic() > entry.expires_at:
            self._data.pop(self._key(key), None)
            return None
        return entry.value

    def set(self, key: str, value: object, ttl_seconds: int | None = None) -> None:
        self._data[self._key(key)] = _Entry(value, ttl_seconds)

    def invalidate(self, key: str) -> None:
        self._data.pop(self._key(key), None)

    def _key(self, key: str) -> str:
        return f"{self._version}:{key}"
