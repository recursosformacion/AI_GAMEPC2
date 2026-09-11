import hashlib
import time
from collections.abc import Callable
from typing import cast

from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.evidence_engine import EvidenceEngine
from src.osap.application.execution_plan import AggregatedProviderResult
from src.osap.application.library_manager import LibraryManager
from src.osap.application.merge_service import DefaultMergeService
from src.osap.application.provider_orchestrator import ProviderOrchestrator
from src.osap.application.provider_orchestrator import ProviderReport as ProviderReport
from src.osap.application.ranker import DefaultWorkRanker
from src.osap.application.work_grouper import WorkGrouper
from src.osap.application.work_merge_service import _sort_key
from src.osap.application.work_resolver import WorkResolver
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.errors import ResourceUnavailableError, ScoreResolutionError
from src.osap.domain.evidence import Evidence, EvidenceMetrics, EvidenceReason, EvidenceReasonKind
from src.osap.domain.ranking import RankingContext, RankingPolicy, UserPreferences
from src.osap.domain.ranking_config import RankingConfig
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.resolve_result import ResolveResult
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import Duration, LibraryId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.ranking_engine import IRankingEngine

_QUALITY_VALUE: dict[str, float] = {
    "unreadable": 0.1,
    "reader": 0.4,
    "good_reader": 0.7,
    "high_quality": 0.95,
}

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
        # Pipeline V2.1 (F4.E): agrupar obras (WorkGrouper) → rankear obra
        # (DefaultWorkRanker) → elegir representación por preferencia de adquisición.
        self._work_grouper = WorkGrouper()
        self._work_ranker = DefaultWorkRanker()
        self._work_merger = DefaultMergeService()
        self._work_policy = RankingPolicy()

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
            work_score: float | None = None
            chosen = self._pick(ranking, index)
        else:
            result = self._collect(request, on_progress)
            candidates = result.candidates
            providers = list(result.providers_used)
            diagnostics = list(result.diagnostics)
            if not candidates:
                ranking = ()
                work_score = None
                chosen = None
            else:
                # F4.E (V2.1): representaciones → agrupación en obras → score de obra →
                # representación elegida dentro de la mejor obra por preferencia.
                groups = self._work_grouper.group(candidates)
                query_descriptor = WorkDescriptor(
                    work_id=WorkId("resolution"),
                    title=(request.title or request.query or " "),
                    composer=request.composer,
                )
                ranked_works = self._work_ranker.rank(
                    groups,
                    RankingContext(query_descriptor=query_descriptor, user_preferences=UserPreferences()),
                    self._work_policy,
                )
                best_group = ranked_works.order[0].work
                work_score = ranked_works.order[0].score
                ranking = tuple(sorted(best_group.representations, key=_sort_key))
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
            evidence = self._build_evidence(chosen, work_score)

        return ResolveResult(
            request=request,
            selected_work=work,
            chosen=chosen,
            ranking=ranking,
            providers_used=tuple(providers),
            duration=duration,
            selection_reason="Mejor obra por DefaultWorkRanker (V2.1); representación por preferencia de adquisición"
            if chosen is not None
            else "No viable representation could be acquired",
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

    def gather(
        self,
        request: ResolveRequest,
        on_progress: ProgressCallback | None = None,
        on_index_partial: Callable[[tuple[CandidateRepresentation, ...]], None] | None = None,
    ) -> AggregatedProviderResult:
        """Recolecta candidatos de los proveedores SIN el ranking V1.

        La agrupación y el orden de obras los decide la pipeline V2.1 (ADR-0035/F4.C):
        las representaciones son evidencia sin orden predefinido.
        """
        return self._collect(request, on_progress, on_index_partial)

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
    def _build_evidence(chosen: CandidateRepresentation, work_score: float | None) -> Evidence:
        """Explicación estructural V2.1 de la representación elegida (sin EvidenceEngine V1)."""
        confidence = chosen.confidence.value
        reasons = (
            EvidenceReason(EvidenceReasonKind.CONFIDENCE, True, f"confidence={confidence:.2f}"),
            EvidenceReason(EvidenceReasonKind.FORMAT, bool(chosen.downloadable), chosen.format.value),
            EvidenceReason(
                EvidenceReasonKind.PUBLIC_DOMAIN,
                bool(chosen.public_domain),
                "public_domain" if chosen.public_domain else "not_public_domain",
            ),
            EvidenceReason(
                EvidenceReasonKind.COMPLETENESS,
                chosen.completeness >= 1.0,
                f"completeness={chosen.completeness}",
            ),
        )
        quality_value = _QUALITY_VALUE.get(chosen.quality.name.lower(), 0.5)
        return Evidence(
            provider_id=chosen.provider_id,
            reasons=reasons,
            metrics=EvidenceMetrics(
                confidence=confidence,
                quality=quality_value,
                completeness=chosen.completeness,
            ),
            checksum=chosen.checksum,
            ranking_score=work_score or 0.0,
        )

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
