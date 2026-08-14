"""Batch work resolution use case (v1).

Takes a list of works, resolves each one (work first, then composer identity) reusing
`ResolveComposerUseCase`, with bounded concurrency. Read-only: never writes to storage.
Each work resolves independently; a failure in one does not abort the batch.
"""

import asyncio
from dataclasses import dataclass

from src.osap.application.composer_resolution_engine import ResolutionDecision
from src.osap.application.use_cases.resolve_composer import ResolveComposerUseCase


@dataclass(frozen=True)
class WorkResolveInput:
    id: str | None
    composer: str | None
    work_title: str | None
    work_catalog: str | None
    work_year: int | None
    source_provider: str | None
    source_work_id: str | None


@dataclass(frozen=True)
class ResolvedWorkItem:
    id: str | None
    input: WorkResolveInput
    decision: ResolutionDecision
    error: str | None = None


class ResolveWorksUseCase:
    def __init__(self, resolve_composer: ResolveComposerUseCase) -> None:
        self._resolve_composer = resolve_composer

    async def execute(
        self,
        works: list[WorkResolveInput],
        concurrency: int = 4,
    ) -> list[ResolvedWorkItem]:
        if concurrency < 1:
            concurrency = 1
        semaphore = asyncio.Semaphore(concurrency)

        async def one(work: WorkResolveInput) -> ResolvedWorkItem:
            async with semaphore:
                try:
                    decision = await self._resolve_composer.execute(
                        composer=work.composer,
                        work_title=work.work_title,
                        work_catalog=work.work_catalog,
                        work_year=work.work_year,
                        source_provider=work.source_provider,
                        source_work_id=work.source_work_id,
                    )
                    return ResolvedWorkItem(id=work.id, input=work, decision=decision)
                except Exception as exc:  # noqa: BLE001
                    return ResolvedWorkItem(id=work.id, input=work, decision=decision_placeholder(), error=str(exc))

        return list(await asyncio.gather(*(one(w) for w in works)))


def decision_placeholder() -> ResolutionDecision:
    from src.osap.application.composer_resolution_engine import ResolutionDecision

    return ResolutionDecision(
        status="not_found",
        composer=None,
        confidence=0.0,
        input_quality="normal",
    )
