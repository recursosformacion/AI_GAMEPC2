import concurrent.futures
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from src.osap.application.catalog_manager import CatalogManager
from src.osap.application.execution_plan import (
    AggregatedProviderResult,
    ProviderExecutionPlan,
    ProviderStep,
    cost_rank,
)
from src.osap.application.provider_result_aggregator import ProviderResultAggregator
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.errors import ResourceUnavailableError, ScoreResolutionError
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import ProviderId
from src.osap.ports.cache import ICache
from src.osap.ports.catalog_provider import ICatalogProvider

# Normalized provider statuses (the only values visible to the user/UI).
STATUS_OK = "ok"

logger = logging.getLogger("osap.api.orchestrator")

# Phase 2 bound: the search waits at most this long for providers; slower ones are
# marked unavailable and the Work Resolution is returned with what arrived (ADR-0020).
# Kept above the providers' own HTTP timeouts (e.g. OMR allows up to 10s) so that slow
# but valid providers are NOT dropped and their representations still reach the result.
SEARCH_TIMEOUT_SECONDS = 12.0
STATUS_NO_RESULT = "no_result"
STATUS_UNAVAILABLE = "unavailable"
STATUS_ERROR = "error"

ProgressCallback = Callable[[str], None]

_DEFAULT_CACHE_TTL_SECONDS = 180


@dataclass(frozen=True)
class ProviderReport:
    """Normalized outcome of querying a single catalog provider."""

    provider_id: ProviderId
    outcome: str  # ok | no_result | unavailable | error
    detail: str = ""


class ProviderOrchestrator:
    """Decides whom to ask, in what order, when to stop and when to reuse.

    This is the "brain" of multi-provider resolution. It only knows
    `ICatalogProvider` and `SearchRequest`; it never knows datasets, Hugging
    Face, OMR specifics or costs. Providers are all equal.
    """

    def __init__(
        self,
        catalog_manager: CatalogManager,
        cache: ICache | None = None,
        cache_ttl_seconds: int = _DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._catalog_manager = catalog_manager
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    def search(
        self, search: SearchRequest, on_progress: ProgressCallback | None = None
    ) -> AggregatedProviderResult:
        cached = self._cached(search)
        if cached is not None:
            return cached

        plan = self._build_plan(search)
        result = self._execute(plan, search, on_progress)
        self._store(search, result)
        return result

    def provider_status(
        self, search: SearchRequest, on_progress: ProgressCallback | None = None
    ) -> tuple[ProviderReport, ...]:
        reports: list[ProviderReport] = []
        for provider in self._catalog_manager.providers():
            pid = provider.provider_id.value
            if not self._eligible(provider, search):
                reports.append(ProviderReport(provider.provider_id, STATUS_UNAVAILABLE, ""))
                continue
            if on_progress is not None:
                on_progress(f"Consultando {pid}...")
            try:
                candidates = provider.search(search)
            except ResourceUnavailableError as exc:
                reports.append(ProviderReport(provider.provider_id, STATUS_UNAVAILABLE, exc.code or str(exc)))
                continue
            except (ScoreResolutionError, NotImplementedError) as exc:
                reports.append(ProviderReport(provider.provider_id, STATUS_ERROR, str(exc)))
                continue
            if candidates:
                formats = ", ".join(sorted({c.format.value for c in candidates}))
                reports.append(ProviderReport(provider.provider_id, STATUS_OK, formats))
            else:
                reports.append(ProviderReport(provider.provider_id, STATUS_NO_RESULT, ""))
        return tuple(reports)

    def provider(self, provider_id: ProviderId) -> ICatalogProvider:
        for provider in self._catalog_manager.providers():
            if provider.provider_id == provider_id:
                return provider
        raise ScoreResolutionError(f"No catalog provider registered for {provider_id.value!r}")

    def _build_plan(self, search: SearchRequest) -> ProviderExecutionPlan:
        eligible = [p for p in self._catalog_manager.providers() if self._eligible(p, search)]
        eligible.sort(key=lambda p: cost_rank(p.capabilities().cost_level))
        steps = tuple(
            ProviderStep(provider_id=p.provider_id, cost_level=p.capabilities().cost_level, stop_if_found=True)
            for p in eligible
        )
        return ProviderExecutionPlan(steps=steps)

    def _execute(
        self, plan: ProviderExecutionPlan, search: SearchRequest, on_progress: ProgressCallback | None
    ) -> AggregatedProviderResult:
        """Phase 2 (enrich): consult ALL eligible providers and merge everything.

        Per ADR-0020 (revised), the search does not stop at the first "sufficient"
        provider: all compatible providers are queried (in parallel) so the Work
        Resolution gathers every representation, metadata and relationship.

        Hybrid mode (estático): cada proveedor está marcado como *indexado* o *en vivo*.
        - Indexados (omr, imslp, mutopia, musicbrainz): se sirven SIEMPRE del índice
          local (nunca en vivo), tenga o no resultados en esta búsqueda.
        - No indexados (RISM, openscore, local): se consultan SIEMPRE en vivo.
        La marca la declara el proveedor de índice (`IndexCatalogProvider.indexed_providers`).
        """
        aggregator = ProviderResultAggregator()

        def run(step: ProviderStep) -> tuple[str, tuple[CandidateRepresentation, ...] | None]:
            provider = self.provider(step.provider_id)
            pid = provider.provider_id.value
            if on_progress is not None:
                on_progress(f"Consultando {pid}...")
            start = time.monotonic()
            try:
                found = provider.search(search)
                elapsed = time.monotonic() - start
                logger.info("provider %s: %d candidato(s) en %.3fs", pid, len(found), elapsed)
                if on_progress is not None:
                    on_progress(f"{pid}: {len(found)} candidato(s)")
                return pid, found
            except (ResourceUnavailableError, ScoreResolutionError, NotImplementedError) as exc:
                elapsed = time.monotonic() - start
                logger.info("provider %s: unavailable en %.3fs (%s)", pid, elapsed, exc)
                return pid, None

        # 1) Descubrir el proveedor de índice y su marca estática de proveedores indexados.
        index_step = next((s for s in plan.steps if s.provider_id.value == "index"), None)
        indexed: set[str] = set()
        if index_step is not None:
            provider = self.provider(index_step.provider_id)
            indexed = set(getattr(provider, "indexed_providers", ()))

        # 2) Proveedores indexados: SOLO índice (aunque devuelva 0 resultados).
        index_results: dict[str, tuple[CandidateRepresentation, ...]] = {}
        if index_step is not None:
            if on_progress is not None:
                on_progress("Consultando índice local...")
            start = time.monotonic()
            try:
                found = self.provider(index_step.provider_id).search(search)
                elapsed = time.monotonic() - start
                logger.info("provider index: %d candidato(s) en %.3fs", len(found), elapsed)
                index_results = _index_by_provider(found)
                for pid, cands in index_results.items():
                    if cands:
                        logger.info("index cubre %s: %d candidato(s)", pid, len(cands))
                        aggregator.add_candidates(ProviderId(pid), cands)
            except (ResourceUnavailableError, ScoreResolutionError, NotImplementedError) as exc:
                logger.info("provider index: unavailable (%s)", exc)
            if on_progress is not None and index_results:
                on_progress(f"índice: {sum(len(c) for c in index_results.values())} candidato(s)")

        # 3) Proveedores NO indexados: SIEMPRE en vivo.
        live_steps = [
            s for s in plan.steps
            if s is not index_step and s.provider_id.value not in indexed
        ]
        found_by_pid: dict[str, tuple[CandidateRepresentation, ...] | None] = {}
        if live_steps:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(len(live_steps), 8))) as executor:
                futures = {executor.submit(run, step): step for step in live_steps}
                done, not_done = concurrent.futures.wait(
                    futures, timeout=SEARCH_TIMEOUT_SECONDS, return_when=concurrent.futures.ALL_COMPLETED
                )
                for future in done:
                    result_pid, result_found = future.result()
                    found_by_pid[result_pid] = result_found
                for future in not_done:
                    step = futures[future]
                    logger.info(
                        "provider %s: timeout (>{:.0f}s), skipped",
                        step.provider_id.value,
                        SEARCH_TIMEOUT_SECONDS,
                    )
                    found_by_pid[step.provider_id.value] = None

        # 4) Agregar en orden de plan para `providers_used` determinista.
        for step in plan.steps:
            pid = step.provider_id.value
            if step is index_step:
                continue
            if pid in indexed:
                continue  # servido por el índice (sus candidatos ya se agregaron)
            found_live = found_by_pid.get(pid)
            if found_live:
                aggregator.add_candidates(step.provider_id, found_live)
            else:
                aggregator.add_diagnostic(f"{pid}: unavailable")
        return aggregator.result()

    def _cached(self, search: SearchRequest) -> AggregatedProviderResult | None:
        if self._cache is None:
            return None
        value = self._cache.get(self._cache_key(search))
        if isinstance(value, AggregatedProviderResult):
            return AggregatedProviderResult(
                groups=value.groups,
                providers_used=value.providers_used,
                diagnostics=value.diagnostics,
                cached=True,
            )
        return None

    def _store(self, search: SearchRequest, result: AggregatedProviderResult) -> None:
        if self._cache is not None:
            self._cache.set(self._cache_key(search), result, ttl_seconds=self._cache_ttl_seconds)

    @staticmethod
    def _cache_key(search: SearchRequest) -> str:
        return f"search:{repr(search)}"

    @staticmethod
    def _eligible(provider: ICatalogProvider, search: SearchRequest) -> bool:
        if search.allowed_providers and provider.provider_id not in search.allowed_providers:
            return False
        if provider.provider_id in search.excluded_providers:
            return False
        caps = provider.capabilities()
        if not search.online and not caps.offline:
            return False
        if not search.offline and caps.offline:
            return False
        requested = {
            "title": search.title,
            "composer": search.composer,
            "catalogue": search.searches_by_catalogue,
            "instrumentation": bool(search.instrumentation),
            "genre": search.searches_by_genre,
            "key": search.searches_by_key,
            "year": search.searches_by_year,
        }
        return all(
            not wants or bool(getattr(caps, f"supports_{field}")) for field, wants in requested.items()
        )


def _index_by_provider(
    candidates: tuple[CandidateRepresentation, ...],
) -> dict[str, tuple[CandidateRepresentation, ...]]:
    """Agrupa los candidatos del índice por su provider_id real."""
    by_provider: dict[str, list[CandidateRepresentation]] = {}
    for candidate in candidates:
        pid = candidate.provider_id.value
        if pid == "index":
            continue
        by_provider.setdefault(pid, []).append(candidate)
    return {pid: tuple(cands) for pid, cands in by_provider.items()}
