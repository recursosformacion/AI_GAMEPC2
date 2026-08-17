"""Wikidata identity resolver (v2, alias-aware).

Resuelve un nombre de compositor (p. ej. "W.A. Mozart") a la persona real en Wikidata
("Wolfgang Amadeus Mozart") y devuelve sus identificadores estables (QID, ISNI, VIAF,
LCCN, MusicBrainz). Usa `composer_identifiers` (búsqueda alias-aware por canonical +
apellido), reutilizando la infraestructura de identidad ya construida.

Antes: match por label exacto → "W.A. Mozart" no encontraba a Mozart ni adjuntaba IDs.
Ahora: la identidad se enriquece y el motor puede decidir resolved por identidad fuerte.
"""

from __future__ import annotations

import asyncio

from src.osap.infrastructure.identifiers.open_sources import composer_identifiers
from src.osap.ports.composer_resolver import (
    IComposerResolver,
    ResolverCandidate,
    ResolverCategory,
    ResolverEvidence,
    ResolverQuery,
    ResolverResult,
)

_IDENTITY_CONFIDENCE = 0.9


class WikidataIdentityResolver(IComposerResolver):
    provider_id = "wikidata"
    categories = frozenset({ResolverCategory.IDENTITY})

    async def resolve(self, query: ResolverQuery) -> ResolverResult:
        name = (query.composer or "").strip()
        if not name:
            return ResolverResult(provider=self.provider_id, candidates=())
        try:
            record = await asyncio.to_thread(composer_identifiers, name)
        except Exception:  # noqa: BLE001
            return ResolverResult(provider=self.provider_id, candidates=())
        if record is None:
            return ResolverResult(provider=self.provider_id, candidates=())

        external_ids: dict[str, str] = {}
        for attr, key in (
            ("wikidata", "qid"),
            ("isni", "isni"),
            ("viaf", "viaf"),
            ("lccn", "lccn"),
            ("musicbrainz", "musicbrainz"),
        ):
            value = getattr(record, attr, None)
            if value:
                external_ids[key] = str(value)

        if not external_ids:
            return ResolverResult(provider=self.provider_id, candidates=())

        candidate = ResolverCandidate(
            name=str(record.canonical_name or name),
            confidence=_IDENTITY_CONFIDENCE,
            aliases=tuple(record.aliases or ()),
            external_ids=external_ids,
            evidence=(ResolverEvidence(kind="external_id", confidence=_IDENTITY_CONFIDENCE),),
        )
        return ResolverResult(provider=self.provider_id, candidates=(candidate,))
