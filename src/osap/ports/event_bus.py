from abc import ABC, abstractmethod
from collections.abc import Callable

from ..domain.event import Event


class IEventBus(ABC):
    """Publishes domain events for UI progress, monitoring and logs."""

    @abstractmethod
    def publish(self, event: Event) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        raise NotImplementedError
