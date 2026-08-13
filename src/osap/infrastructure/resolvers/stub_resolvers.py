"""Disabled resolver stubs (v1).

Placeholders for future sources. They expose the `IComposerResolver` contract and their
category so the orchestrator can target them later, but currently return no candidates
(disabled). CPDL will be a CATALOG `work_match` source; MusicBrainz/Wikidata are IDENTITY
authority sources.

Each needs a data source/credentials before it can return real candidates.
"""

from src.osap.ports.composer_resolver import (
    IComposerResolver,
    ResolverCategory,
    ResolverQuery,
    ResolverResult,
)


class _DisabledResolver(IComposerResolver):
    provider_id = "stub"
    categories = frozenset()

    async def resolve(self, query: ResolverQuery) -> ResolverResult:
        return ResolverResult(provider=self.provider_id, candidates=())


class CPDLResolver(_DisabledResolver):
    provider_id = "cpdl"
    categories = frozenset({ResolverCategory.CATALOG})


class MusicBrainzResolver(_DisabledResolver):
    provider_id = "musicbrainz"
    categories = frozenset({ResolverCategory.IDENTITY})


class WikidataResolver(_DisabledResolver):
    provider_id = "wikidata"
    categories = frozenset({ResolverCategory.IDENTITY})
