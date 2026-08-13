"""Work → composer matching (v1).

Reuses the existing `WorkResolutionEngine` to find the work in OSAP's known catalogs and
extract the composers associated with the matches. This is the CATALOG phase of composer
resolution: the work is the primary signal, and each matched work's composer is returned
as a candidate tagged with the catalog provider that produced it.

It never resolves identity: it only surfaces `(provider, composer_name)` evidence for the
`ComposerResolutionEngine` to merge with the IDENTITY resolvers.
"""

from src.osap.application.work_resolution_engine import WorkResolutionEngine
from src.osap.domain.resolve_request import ResolveRequestBuilder
from src.osap.ports.composer_resolver import (
    ResolverCandidate,
    ResolverEvidence,
    ResolverQuery,
)


class WorkComposerMatcher:
    def __init__(self, engine: WorkResolutionEngine) -> None:
        self._engine = engine

    def match(self, query: ResolverQuery) -> list[tuple[str, ResolverCandidate]]:
        """Resolve the work and return (catalog provider, composer candidate) pairs."""
        if not query.work_title:
            return []
        builder = ResolveRequestBuilder().title(query.work_title)
        if query.composer:
            builder = builder.composer(query.composer)
        result = self._engine.resolve(builder.build())

        best: dict[tuple[str, str], tuple[float, ResolverCandidate]] = {}
        for candidate in result.ranking:
            composer = candidate.work_descriptor.composer
            if not composer:
                continue
            provider = candidate.provider_id.value
            confidence = candidate.confidence.value
            key = (provider, composer)
            existing = best.get(key)
            if existing is None or confidence > existing[0]:
                evidence = (
                    ResolverEvidence(
                        kind="work_match",
                        confidence=confidence,
                        work_title=candidate.work_descriptor.title,
                        work_catalog=candidate.work_descriptor.catalogue_number,
                    ),
                )
                best[key] = (
                    confidence,
                    ResolverCandidate(name=composer, confidence=confidence, evidence=evidence),
                )
        return [(provider, candidate) for (provider, _), (_, candidate) in best.items()]
