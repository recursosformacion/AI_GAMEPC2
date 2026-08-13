"""Canonical identity resolver (v1).

Local identity source backed by the central composer alias table
(`MetadataNormalizer.canonical_composer` + `resources/canonical`). It is the first
functional resolver: for a known composer name it returns the canonical identity and
treats the input name as an alias. It never invents an identity — unknown names yield no
candidates.
"""

from src.osap.application.metadata_normalizer import _KNOWN_COMPOSERS, MetadataNormalizer
from src.osap.ports.composer_resolver import (
    IComposerResolver,
    ResolverCandidate,
    ResolverCategory,
    ResolverEvidence,
    ResolverQuery,
    ResolverResult,
)

_KNOWN_VALUES = {canonical.lower() for canonical in _KNOWN_COMPOSERS.values()}


class CanonicalComposerResolver(IComposerResolver):
    provider_id = "canonical"
    categories = frozenset({ResolverCategory.IDENTITY})

    async def resolve(self, query: ResolverQuery) -> ResolverResult:
        raw = (query.composer or "").strip()
        if not raw:
            return ResolverResult(provider=self.provider_id, candidates=())
        canonical = MetadataNormalizer.canonical_composer(raw)
        if not canonical or canonical.lower() not in _KNOWN_VALUES:
            return ResolverResult(provider=self.provider_id, candidates=())

        evidence: tuple[ResolverEvidence, ...] = (
            ResolverEvidence(kind="alias", confidence=0.9, work_title=query.work_title),
        )
        candidate = ResolverCandidate(
            name=canonical,
            confidence=0.9,
            aliases=() if canonical == raw else (raw,),
            evidence=evidence,
        )
        return ResolverResult(provider=self.provider_id, candidates=(candidate,))
