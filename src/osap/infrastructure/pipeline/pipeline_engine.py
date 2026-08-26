"""Motor de pipeline mínimo (compone stages y los ejecuta en orden)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.osap.domain.event import Event
from src.osap.ports.pipeline_engine import IPipelineEngine

if TYPE_CHECKING:
    from src.osap.domain.pipeline_context import PipelineContext
    from src.osap.ports.event_bus import IEventBus
    from src.osap.ports.pipeline_stage import IPipelineStage


class PipelineEngine(IPipelineEngine):
    """Ejecuta los stages registrados en orden sobre el `PipelineContext`.

    Es el contenedor del Score Acquisition Pipeline: los stages (p. ej.
    `ScoreValidationStage`) se añaden dinámicamente sin modificar el motor.
    Si se inyecta un `IEventBus`, publica un evento por stage ejecutado.
    """

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        self._stages: list[IPipelineStage] = []

    def add_stage(self, stage: IPipelineStage) -> None:
        self._stages.append(stage)

    def run(self, context: PipelineContext) -> PipelineContext:
        current = context
        for stage in self._stages:
            self._publish("StageStarted", stage.name, current.request)
            current = stage.execute(current)
            if self._event_bus is not None:
                self._event_bus.publish(
                    Event(
                        event_type=f"pipeline.stage.{stage.name}",
                        payload={"stage": stage.name},
                    )
                )
        return current

    def _publish(self, event_type: str, stage_name: str, request: object) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(
            Event(
                event_type=event_type,
                aggregate_id=stage_name,
                payload={"stage": stage_name},
            )
        )

    @property
    def stages(self) -> tuple[IPipelineStage, ...]:
        return tuple(self._stages)
