"""Composer identity resolution use case (v1).

Read-only operation: builds a `ResolverQuery` from the caller context, classifies input
quality, runs the resolution engine and returns the decision. It never writes to storage.
"""

from src.osap.application.composer_resolution_engine import (
    ComposerResolutionEngine,
    ResolutionDecision,
)
from src.osap.application.input_quality import classify_input_quality
from src.osap.ports.composer_resolver import (
    ResolverQuery,
    ResolverRepresentation,
)


class ResolveComposerUseCase:
    def __init__(self, engine: ComposerResolutionEngine) -> None:
        self.engine = engine

    async def execute(
        self,
        composer: str | None = None,
        work_title: str | None = None,
        work_catalog: str | None = None,
        work_year: int | None = None,
        source_provider: str | None = None,
        source_work_id: str | None = None,
        representations: list[ResolverRepresentation] | None = None,
    ) -> ResolutionDecision:
        query = ResolverQuery(
            work_title=work_title,
            composer=composer,
            work_catalog=work_catalog,
            work_year=work_year,
            source_provider=source_provider,
            source_work_id=source_work_id,
            representations=tuple(representations or ()),
        )
        # El nombre del compositor es evidencia secundaria y puede faltar: sin nombre no hay
        # calidad de entrada que juzgar.
        input_quality = classify_input_quality(composer) if composer else "normal"
        return await self.engine.resolve(query, input_quality)
