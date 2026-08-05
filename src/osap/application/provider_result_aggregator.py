from src.osap.application.execution_plan import AggregatedProviderResult, WorkGroup
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.normalization import normalize_name
from src.osap.domain.value_objects import ProviderId
from src.osap.domain.work_descriptor import WorkDescriptor


class ProviderResultAggregator:
    """Unifies the results produced by the providers of an execution plan.

    Responsibilities:
    - receive the results of every provider executed by the orchestrator;
    - group `CandidateRepresentation` by `WorkDescriptor`;
    - drop trivial duplicates (same provider + same remote id, checksum when present);
    - normalize the collection so the ranking engine always gets the same structure;
    - keep diagnostics and the provenance of each candidate.

    It never ranks, never applies evidence, never downloads, never mutates a
    `CandidateRepresentation` and never knows a concrete provider.
    """

    def __init__(self) -> None:
        self._items: list[tuple[ProviderId, CandidateRepresentation]] = []
        self._providers_used: list[ProviderId] = []
        self._diagnostics: list[str] = []

    def add_candidates(self, provider_id: ProviderId, candidates: tuple[CandidateRepresentation, ...]) -> None:
        self._providers_used.append(provider_id)
        self._items.extend((provider_id, candidate) for candidate in candidates)

    def add_diagnostic(self, message: str) -> None:
        self._diagnostics.append(message)

    def result(self, cached: bool = False) -> AggregatedProviderResult:
        deduped = self._deduplicate(self._items)
        groups = self._group(deduped)
        return AggregatedProviderResult(
            groups=groups,
            providers_used=tuple(self._providers_used),
            diagnostics=tuple(self._diagnostics),
            cached=cached,
        )

    @staticmethod
    def _deduplicate(
        items: list[tuple[ProviderId, CandidateRepresentation]]
    ) -> list[tuple[ProviderId, CandidateRepresentation]]:
        seen: set[tuple[object, ...]] = set()
        out: list[tuple[ProviderId, CandidateRepresentation]] = []
        for provider_id, candidate in items:
            key = _dedup_key(provider_id, candidate)
            if key is None:
                out.append((provider_id, candidate))
                continue
            if key in seen:
                continue
            seen.add(key)
            out.append((provider_id, candidate))
        return out

    @staticmethod
    def _group(items: list[tuple[ProviderId, CandidateRepresentation]]) -> tuple[WorkGroup, ...]:
        order: list[tuple[object, ...]] = []
        buckets: dict[tuple[object, ...], list[CandidateRepresentation]] = {}
        providers: dict[tuple[object, ...], set[str]] = {}
        for provider_id, candidate in items:
            key = _identity_key(candidate.work_descriptor)
            if key not in buckets:
                order.append(key)
                buckets[key] = []
                providers[key] = set()
            buckets[key].append(candidate)
            providers[key].add(provider_id.value)
        groups: list[WorkGroup] = []
        for key in order:
            representations = tuple(buckets[key])
            groups.append(
                WorkGroup(
                    work=representations[0].work_descriptor,
                    representations=representations,
                    providers=tuple(ProviderId(p) for p in sorted(providers[key])),
                )
            )
        return tuple(groups)


def _dedup_key(provider_id: ProviderId, candidate: CandidateRepresentation) -> tuple[object, ...] | None:
    if candidate.remote_id:
        return (provider_id.value, "remote", candidate.remote_id)
    if candidate.checksum:
        return (provider_id.value, "checksum", candidate.checksum)
    return None


def _identity_key(work: WorkDescriptor) -> tuple[object, ...]:
    identifiers = tuple(sorted((identifier.kind, identifier.value) for identifier in work.identifiers))
    return (
        normalize_name(work.title),
        normalize_name(work.composer or ""),
        work.catalogue_number or "",
        work.opus or "",
        identifiers,
    )
