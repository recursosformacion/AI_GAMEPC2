import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.library_manager import LibraryManager
from src.osap.application.work_merge_service import _sort_key
from src.osap.application.work_resolver import WorkResolver
from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.errors import ResourceUnavailableError, ScoreResolutionError
from src.osap.domain.ranking_config import RankingConfig
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.resolve_result import ResolveResult
from src.osap.domain.value_objects import Duration, LibraryId, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.ports.catalog_provider import ICatalogProvider
from src.osap.ports.ranking_engine import IRankingEngine

# Normalized provider statuses (the only values visible to the user/UI).
STATUS_OK = "ok"
STATUS_NO_RESULT = "no_result"
STATUS_UNAVAILABLE = "unavailable"
STATUS_ERROR = "error"

_STRUCTURED_FORMATS = ("musicxml", "mei")

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class ProviderReport:
    """Normalized outcome of querying a single catalog provider."""

    provider_id: ProviderId
    outcome: str  # ok | no_result | unavailable | error
    detail: str = ""


def _notify(on_progress: ProgressCallback | None, message: str) -> None:
    if on_progress is not None:
        on_progress(message)


class WorkResolutionEngine:
    """Resolves a musical request into a ResolveResult.

    The engine only knows `ICatalogProvider` and `CandidateRepresentation`. It
    never knows datasets, Hugging Face, PDMX, sizes or downloads: each provider
    self-manages its own availability and raises `ResourceUnavailableError` when
    it cannot serve.
    """

    def __init__(
        self,
        catalog_manager: CatalogManager,
        ranking_engine: IRankingEngine,
        work_resolver: WorkResolver,
        config: RankingConfig,
        library_manager: LibraryManager | None = None,
    ) -> None:
        self._catalog_manager = catalog_manager
        self._ranking_engine = ranking_engine
        self._work_resolver = work_resolver
        self._config = config
        self._library_manager = library_manager

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
            candidates, providers, diagnostics = self._collect(request, on_progress)
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

        return ResolveResult(
            request=request,
            selected_work=work,
            chosen=chosen,
            ranking=ranking,
            providers_used=tuple(providers),
            duration=duration,
            selection_reason=f"Top-ranked by RankingEngine (provider {chosen.provider_id.value})",
            local_path=local_path,
            score_id=score_id,
            downloaded=downloaded,
            diagnostics=tuple(diagnostics),
        )

    def download(self, candidate: CandidateRepresentation, request: ResolveRequest) -> AcquisitionResult:
        provider = self._find(candidate.provider_id)
        return provider.download(candidate, request.desired_format)

    def rank(
        self, request: ResolveRequest, on_progress: ProgressCallback | None = None
    ) -> tuple[CandidateRepresentation, ...]:
        candidates, _, _ = self._collect(request, on_progress)
        return self._ranking_engine.rank(candidates, request, self._config)

    def provider_status(
        self, request: ResolveRequest, on_progress: ProgressCallback | None = None
    ) -> tuple[ProviderReport, ...]:
        reports: list[ProviderReport] = []
        for provider in self._catalog_manager.providers():
            pid = provider.provider_id.value
            if not self._eligible(provider, request):
                reports.append(ProviderReport(provider.provider_id, STATUS_UNAVAILABLE, ""))
                _notify(on_progress, f"{pid}: omitido")
                continue
            _notify(on_progress, f"Consultando {pid}...")
            try:
                candidates = provider.search(request)
            except ResourceUnavailableError as exc:
                reports.append(ProviderReport(provider.provider_id, STATUS_UNAVAILABLE, exc.code or str(exc)))
                _notify(on_progress, f"{pid}: no disponible")
                continue
            except (ScoreResolutionError, NotImplementedError) as exc:
                reports.append(ProviderReport(provider.provider_id, STATUS_ERROR, str(exc)))
                _notify(on_progress, f"{pid}: error")
                continue
            if candidates:
                formats = ", ".join(sorted({c.format.value for c in candidates}))
                reports.append(ProviderReport(provider.provider_id, STATUS_OK, formats))
                _notify(on_progress, f"{pid}: {len(candidates)} candidato(s)")
            else:
                reports.append(ProviderReport(provider.provider_id, STATUS_NO_RESULT, ""))
                _notify(on_progress, f"{pid}: sin resultados")
        return tuple(reports)

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
        self, request: ResolveRequest, on_progress: ProgressCallback | None = None
    ) -> tuple[tuple[CandidateRepresentation, ...], list[ProviderId], list[str]]:
        results: list[CandidateRepresentation] = []
        used: list[ProviderId] = []
        diagnostics: list[str] = []
        for provider in self._catalog_manager.providers():
            if not self._eligible(provider, request):
                continue
            used.append(provider.provider_id)
            pid = provider.provider_id.value
            _notify(on_progress, f"Consultando {pid}...")
            try:
                found = provider.search(request)
            except (ResourceUnavailableError, ScoreResolutionError, NotImplementedError):
                diagnostics.append(f"{pid}: unavailable")
                _notify(on_progress, f"{pid}: no disponible")
                continue
            _notify(on_progress, f"{pid}: {len(found)} candidato(s)")
            results.extend(found)
        return tuple(results), used, diagnostics

    @staticmethod
    def _eligible(provider: ICatalogProvider, request: ResolveRequest) -> bool:
        if request.allowed_providers and provider.provider_id not in request.allowed_providers:
            return False
        if provider.provider_id in request.excluded_providers:
            return False
        caps = provider.capabilities()
        if not request.online and not caps.offline:
            return False
        return not (not request.offline and caps.offline)

    def _find(self, provider_id: ProviderId) -> ICatalogProvider:
        for provider in self._catalog_manager.providers():
            if provider.provider_id == provider_id:
                return provider
        raise ScoreResolutionError(f"No catalog provider registered for {provider_id.value!r}")


def _is_structured(format: object) -> bool:
    return getattr(format, "value", "") in _STRUCTURED_FORMATS
