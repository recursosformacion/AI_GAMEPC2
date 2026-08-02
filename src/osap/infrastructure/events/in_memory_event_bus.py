from collections.abc import Callable

from src.osap.domain.event import Event
from src.osap.ports.event_bus import IEventBus


class InMemoryEventBus(IEventBus):
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Event], None]]] = {}
        self.published: list[Event] = []

    def publish(self, event: Event) -> None:
        self.published.append(event)
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        self._handlers.setdefault(event_type, []).append(handler)
