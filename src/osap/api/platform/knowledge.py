"""PlatformApi: mixin de knowledge (F5.4)."""


from src.osap.api.contracts import (
    KnowledgeFactDTO,
    KnowledgeObservationDTO,
    KnowledgeResponse,
    KnowledgeSuggestionDTO,
)
from src.osap.api.platform import _support as _support
from src.osap.api.platform.core import PlatformApiCore

VERSION = "3.1"

















class KnowledgeMixin(PlatformApiCore):
    def knowledge(self) -> KnowledgeResponse:
        base = self._knowledge.base()
        return KnowledgeResponse(
            observations=[
                KnowledgeObservationDTO(
                    execution_id=o.execution_id,
                    source=o.source.value,
                    field=o.field,
                    value=o.value,
                    provider=o.provider,
                )
                for o in base.observations
            ],
            facts=[
                KnowledgeFactDTO(fact_type=f.fact_type.value, field=f.field, value=f.value, count=f.count)
                for f in base.facts
            ],
            suggestions=[
                KnowledgeSuggestionDTO(
                    suggestion_type=s.suggestion_type.value,
                    field=s.field,
                    source_value=s.source_value,
                    target_value=s.target_value,
                    reason=s.reason,
                )
                for s in base.suggestions
            ],
        )

    # --- system -------------------------------------------------------------

