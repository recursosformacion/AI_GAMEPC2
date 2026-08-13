"""Wikidata identity resolver (v1).

Identity authority source via Wikidata SPARQL — block-free (no Cloudflare). Resolves a
composer name to its canonical Wikidata item, aliases and stable external identifiers
(CPDL P4712, MusicBrainz P434, VIAF P214). This addresses the 35k-composer identity
problem: once a stable external id is found, OSAP stops depending on surface name variants.

Uses only the standard library (urllib) with a transparent User-Agent, per Wikidata policy.
"""

import asyncio
from typing import cast

import requests

from src.osap.ports.composer_resolver import (
    IComposerResolver,
    ResolverCandidate,
    ResolverCategory,
    ResolverEvidence,
    ResolverQuery,
    ResolverResult,
)

_SPARQL_URL = "https://query.wikidata.org/sparql"
_USER_AGENT = "osap-resolver/0.1 (contact: osap@example.com)"

# Autoridad: coincidencia exacta de label. El motor pondera y cruza con otras fuentes.
_EXACT_MATCH_CONFIDENCE = 0.85


class WikidataIdentityResolver(IComposerResolver):
    provider_id = "wikidata"
    categories = frozenset({ResolverCategory.IDENTITY})

    async def resolve(self, query: ResolverQuery) -> ResolverResult:
        name = (query.composer or "").strip()
        if not name:
            return ResolverResult(provider=self.provider_id, candidates=())
        try:
            data = await asyncio.to_thread(self._query, name)
        except Exception:  # noqa: BLE001
            return ResolverResult(provider=self.provider_id, candidates=())

        candidates: list[ResolverCandidate] = []
        for row in data:
            item = row.get("itemLabel") or row.get("item") or name
            aliases = tuple(a for a in str(row.get("aliases") or "").split("|") if a)
            external_ids: dict[str, str] = {}
            for prop, label in (("cpdlId", "cpdl"), ("mbid", "musicbrainz"), ("viaf", "viaf")):
                value = row.get(prop)
                if value:
                    external_ids[label] = str(value)
            evidence = tuple(
                ResolverEvidence(kind="external_id", confidence=_EXACT_MATCH_CONFIDENCE)
                for prop in ("cpdlId", "mbid", "viaf")
                if row.get(prop)
            )
            candidates.append(
                ResolverCandidate(
                    name=str(item),
                    confidence=_EXACT_MATCH_CONFIDENCE,
                    aliases=aliases,
                    external_ids=external_ids,
                    evidence=evidence,
                )
            )
        return ResolverResult(provider=self.provider_id, candidates=tuple(candidates))

    @staticmethod
    def _query(name: str) -> list[dict[str, object]]:
        safe = name.replace('"', "").replace("\\", "")
        query = f"""
SELECT ?item ?itemLabel ?cpdlId ?mbid ?viaf
       (GROUP_CONCAT(?alias; separator="|") AS ?aliases) WHERE {{
  ?item rdfs:label "{safe}"@en .
  ?item wdt:P31 wd:Q5 .
  OPTIONAL {{ ?item wdt:P4712 ?cpdlId }}
  OPTIONAL {{ ?item wdt:P434 ?mbid }}
  OPTIONAL {{ ?item wdt:P214 ?viaf }}
  OPTIONAL {{ ?item skos:altLabel ?alias . FILTER(LANG(?alias)="en") }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
GROUP BY ?item ?itemLabel ?cpdlId ?mbid ?viaf
LIMIT 10
"""
        url = _SPARQL_URL
        response = requests.get(
            url,
            params={"query": query, "format": "json"},
            headers={"User-Agent": _USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        payload = cast("dict[str, object]", response.json())
        results = cast("dict[str, object]", payload.get("results", {}))
        bindings = cast("list[object]", results.get("bindings", []))
        out: list[dict[str, object]] = []
        for binding in bindings:
            row: dict[str, object] = {}
            for key, val in cast("dict[str, object]", binding).items():
                if isinstance(val, dict):
                    row[key] = val.get("value")
            out.append(row)
        return out
