from src.osap.domain.pipeline_context import PipelineContext
from src.osap.infrastructure.events import InMemoryEventBus
from src.osap.ports.pipeline_engine import IPipelineEngine
from src.osap.ports.pipeline_stage import IPipelineStage


class PipelineEngine(IPipelineEngine):
    """Composes pipeline stages dynamically. Stages are plugins; the engine
    never knows their internals."""

    def __init__(self, event_bus: InMemoryEventBus) -> None:
        self._event_bus = event_bus
        self._stages: list[IPipelineStage] = []

    def add_stage(self, stage: IPipelineStage) -> None:
        self._stages.append(stage)

    def run(self, context: PipelineContext) -> PipelineContext:
        current = context
        for stage in self._stages:
            self._publish("StageStarted", stage.name, context.request)
            try:
                current = stage.execute(current)
            except Exception as exc:  # noqa: BLE001
                self._publish("StageFailed", stage.name, context.request, {"error": str(exc)})
                raise
            self._publish("StageFinished", stage.name, context.request)
        return current

    def _publish(
        self, event_type: str, stage_name: str, request: object, extra: dict[str, object] | None = None
    ) -> None:
        from src.osap.domain.event import Event

        payload: dict[str, object] = {"stage": stage_name}
        if extra:
            payload.update(extra)
        self._event_bus.publish(Event(event_type=event_type, aggregate_id=stage_name, payload=payload))
