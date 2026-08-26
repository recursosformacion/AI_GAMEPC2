import hashlib
import time
from collections.abc import Callable
from typing import cast

from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.evidence_engine import EvidenceEngine
from src.osap.application.execution_plan import AggregatedProviderResult
from src.osap.application.library_manager import LibraryManager
from src.osap.application.provider_orchestrator import ProviderOrchestrator
from src.osap.application.provider_orchestrator import ProviderReport as ProviderReport
from src.osap.application.work_merge_service import _sort_key
from src.osap.application.work_resolver import WorkResolver
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.errors import ResourceUnavailableError, ScoreResolutionError
from src.osap.domain.ranking_config import RankingConfig
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.resolve_result import ResolveResult
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import Duration, LibraryId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.ranking_engine import IRankingEngine

# Normalized provider statuses (the only values visible to the user/UI).
STATUS_OK = "ok"
STATUS_NO_RESULT = "no_result"
STATUS_UNAVAILABLE = "unavailable"
STATUS_ERROR = "error"

_STRUCTURED_FORMATS = ("musicxml", "mei")

ProgressCallback = Callable[[str], None]


def _notify(on_progress: ProgressCallback | None, message: str) -> None:
    if on_progress is not None:
        on_progress(message)


class WorkResolutionEngine:
    """Resolves a musical request into a ResolveResult.

    The engine only knows `ProviderOrchestrator` and `CandidateRepresentation`;
    it never iterates providers nor knows `CatalogCapabilities`. Deciding whom
    to ask, in what order, when to stop and when to reuse belongs to the
    `ProviderOrchestrator`. Selection belongs to the `IRankingEngine` (evidence),
    never to a provider.
    """

    def __init__(
        self,
        catalog_manager: CatalogManager,
        ranking_engine: IRankingEngine,
        work_resolver: WorkResolver,
        config: RankingConfig,
        library_manager: LibraryManager | None = None,
        orchestrator: ProviderOrchestrator | None = None,
        evidence_engine: EvidenceEngine | None = None,
    ) -> None:
        self._orchestrator = orchestrator or ProviderOrchestrator(catalog_manager)
        self._ranking_engine = ranking_engine
        self._work_resolver = work_resolver
        self._config = config
        self._library_manager = library_manager
        self._evidence_engine = evidence_engine or EvidenceEngine()

    def resolve(
        self,
        request: ResolveRequest,
        download: bool = False,
        index: int | None = None,
        representations: tuple[CandidateRepresentation, ...] | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ResolveResult:
        started = time.monotonic()
        try:
            requested_work = self._work_resolver.resolve(request)
        except ScoreResolutionError:
            requested_work = None

        if representations is not None:
            # Resolution limited to a chosen work's representations: order them
            # by acquisition preference and pick there, never re-scanning other
            # providers/works.
            candidates = tuple(representations)
            ranking = tuple(sorted(candidates, key=_sort_key))
            providers: list[ProviderId] = [c.provider_id for c in candidates]
            diagnostics: list[str] = []
            chosen = self._pick(ranking, index)
        else:
            result = self._collect(request, on_progress)
            candidates = result.candidates
            providers = list(result.providers_used)
            diagnostics = list(result.diagnostics)
            ranking = self._ranking_engine.rank(candidates, request, self._config)
            chosen = self._pick(ranking, index)
        duration = Duration(time.monotonic() - started)

        work = chosen.work_descriptor if chosen is not None else (requested_work or self._fallback_work(request))

        if chosen is None:
            return ResolveResult(
                request=request,
                selected_work=work,
                chosen=None,
                ranking=ranking,
                providers_used=tuple(providers),
                duration=duration,
                selection_reason="No viable representation could be acquired",
                diagnostics=tuple(diagnostics),
            )

        local_path: str | None = None
        downloaded: tuple[str, ...] = ()
        score_id: str | None = None
        manual_fallback: CandidateRepresentation | None = None
        if download:
            attempted: set[str] = set()
            for candidate in ranking:
                pid = candidate.provider_id.value
                if not candidate.downloadable or candidate.manual_download:
                    if manual_fallback is None:
                        manual_fallback = candidate
                    if pid not in attempted:
                        attempted.add(pid)
                        diag = f"{pid}: descarga manual requerida"
                        if candidate.download_url:
                            diag += f" ({candidate.download_url})"
                        diagnostics.append(diag)
                        _notify(on_progress, diag)
                    continue
                _notify(on_progress, f"Descargando {pid}...")
                try:
                    acquisition = self.download(candidate, request)
                except (ResourceUnavailableError, ScoreResolutionError):
                    if pid not in attempted:
                        attempted.add(pid)
                        diagnostics.append(f"{pid}: download unavailable")
                        _notify(on_progress, f"{pid}: descarga no disponible")
                    if manual_fallback is None and candidate.download_url:
                        manual_fallback = candidate
                    continue
                if _is_structured(acquisition.source.format):
                    score_id = hashlib.sha256(cast("bytes", acquisition.source.content)).hexdigest()[:12]  # noqa: S324
                if self._library_manager is not None:
                    identifier = str(candidate.work_descriptor.title)
                    metadata: dict[str, object] = {
                        "provider": candidate.provider_id.value,
                        "format": acquisition.source.format.value,
                        "score_id": score_id,
                    }
                    self._library_manager.store_work(
                        LibraryId("local"), candidate.work_descriptor, acquisition.source, metadata, identifier
                    )
                    local_path = identifier
                    downloaded = (identifier,)
                chosen = candidate
                break

        if chosen is not None and chosen.downloadable is False and manual_fallback is not None:
            chosen = manual_fallback

        evidence = None
        if chosen is not None and ranking:
            scores = self._ranking_engine.rank_detailed(ranking, request, self._config)
            evidence = self._evidence_engine.explain(chosen, request, scores)

        return ResolveResult(
            request=request,
            selected_work=work,
            chosen=chosen,
            ranking=ranking,
            providers_used=tuple(providers),
            duration=duration,
            selection_reason=f"Top-ranked by RankingEngine (provider {chosen.provider_id.value})",
            evidence=evidence,
            local_path=local_path,
            score_id=score_id,
            downloaded=downloaded,
            diagnostics=tuple(diagnostics),
        )

    def download(self, candidate: CandidateRepresentation, request: ResolveRequest) -> AcquisitionResult:
        provider = self._orchestrator.provider(candidate.provider_id)
        return provider.download(candidate, request.desired_format)

    def rank(
        self,
        request: ResolveRequest,
        on_progress: ProgressCallback | None = None,
        on_index_partial: Callable[[tuple[CandidateRepresentation, ...]], None] | None = None,
    ) -> tuple[CandidateRepresentation, ...]:
        result = self._collect(request, on_progress, on_index_partial)
        return self._ranking_engine.rank(result.candidates, request, self._config)

    def provider_status(
        self, request: ResolveRequest, on_progress: ProgressCallback | None = None
    ) -> tuple[ProviderReport, ...]:
        return self._orchestrator.provider_status(SearchRequest.from_resolve(request), on_progress)

    @staticmethod
    def _pick(ranking: tuple[CandidateRepresentation, ...], index: int | None) -> CandidateRepresentation | None:
        if not ranking:
            return None
        if index is not None and index < len(ranking):
            return ranking[index]
        return ranking[0]

    @staticmethod
    def _fallback_work(request: ResolveRequest) -> WorkDescriptor:
        title = (request.title or request.query or "Untitled").strip() or "Untitled"
        return WorkDescriptor(
            work_id=WorkId("work"),
            title=title,
            composer=request.composer,
        )

    def _collect(
        self,
        request: ResolveRequest,
        on_progress: ProgressCallback | None = None,
        on_index_partial: Callable[[tuple[CandidateRepresentation, ...]], None] | None = None,
    ) -> AggregatedProviderResult:
        return self._orchestrator.search(
            SearchRequest.from_resolve(request), on_progress, on_index_partial
        )


def _is_structured(format: object) -> bool:
    return getattr(format, "value", "") in _STRUCTURED_FORMATS
