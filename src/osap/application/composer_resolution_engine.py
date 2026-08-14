"""Composer identity resolution engine (v1).

Runs the `IComposerResolver` plugins, normalizes every candidate centrally with
`MetadataNormalizer.canonical_composer` + the alias table, merges candidates by canonical
identity, aggregates confidence (mean) and decides `resolved | ambiguous | not_found`.

The engine is the only place that knows about canonicalization and the decision rule;
resolvers only return raw candidates and evidence.
"""

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.ports.composer_resolver import (
    IComposerResolver,
    ResolverCandidate,
    ResolverCategory,
    ResolverQuery,
    ResolverResult,
)

# (provider, candidate) pairs produced by the work phase: reuses the existing
# WorkResolutionEngine to find the work and extract its associated composers.
WorkMatchPair = tuple[str, ResolverCandidate]
WorkMatcher = Callable[[ResolverQuery], list[WorkMatchPair]]

RESOLVED_MIN = 0.8
RESOLVED_MARGIN = 0.15


@dataclass(frozen=True)
class ResolvedComposer:
    name: str
    aliases: tuple[str, ...] = ()
    external_ids: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedWork:
    """The best matched work from the work phase (title/catalog)."""

    title: str | None = None
    catalog: str | None = None


@dataclass(frozen=True)
class ResolutionEvidence:
    """A merged evidence item, tagged with the provider that produced it."""

    provider: str
    kind: str
    confidence: float
    work_title: str | None = None
    work_catalog: str | None = None


@dataclass(frozen=True)
class ResolutionCandidate:
    """A merged candidate (one canonical identity)."""

    composer: ResolvedComposer
    confidence: float
    providers: tuple[str, ...] = ()
    evidence: tuple[ResolutionEvidence, ...] = ()


@dataclass(frozen=True)
class ResolutionDecision:
    status: str  # resolved | ambiguous | not_found
    composer: ResolvedComposer | None
    confidence: float
    input_quality: str
    work: ResolvedWork | None = None
    candidates: tuple[ResolutionCandidate, ...] = ()
    evidence: tuple[ResolutionEvidence, ...] = ()


def _canonical_key(name: str) -> str:
    return re.sub(r"\s+", " ", MetadataNormalizer.canonical_composer(name)).strip().lower()


class ComposerResolutionEngine:
    def __init__(
        self,
        resolvers: list[IComposerResolver],
        work_matcher: WorkMatcher | None = None,
    ) -> None:
        self._resolvers = resolvers
        self._work_matcher = work_matcher

    async def resolve(self, query: ResolverQuery, input_quality: str) -> ResolutionDecision:
        raw: list[WorkMatchPair] = self._flatten(await self._run_all(query))
        if self._work_matcher is not None and query.work_title:
            raw.extend(await asyncio.to_thread(self._work_matcher, query))
        resolved_work = self._best_work(raw)
        merged = self._merge(raw)
        merged.sort(key=lambda c: c.confidence, reverse=True)
        evidence = self._collect_evidence(merged)

        if not merged:
            return ResolutionDecision(
                status="not_found",
                composer=None,
                confidence=0.0,
                input_quality=input_quality,
                work=resolved_work,
                candidates=(),
                evidence=evidence,
            )

        top = merged[0]
        second = merged[1].confidence if len(merged) > 1 else 0.0
        if top.confidence >= RESOLVED_MIN and top.confidence - second >= RESOLVED_MARGIN:
            status = "resolved"
        elif len(merged) >= 2:
            status = "ambiguous"
        else:
            status = "not_found"

        return ResolutionDecision(
            status=status,
            composer=top.composer if status == "resolved" else None,
            confidence=top.confidence if status != "not_found" else 0.0,
            input_quality=input_quality,
            work=resolved_work,
            candidates=tuple(merged),
            evidence=evidence,
        )

    @staticmethod
    def _best_work(raw: list[WorkMatchPair]) -> ResolvedWork | None:
        best_title: str | None = None
        best_catalog: str | None = None
        best_conf = -1.0
        for _, candidate in raw:
            for e in candidate.evidence:
                if e.kind == "work_match" and e.work_title and e.confidence > best_conf:
                    best_conf = e.confidence
                    best_title = e.work_title
                    best_catalog = e.work_catalog
        return ResolvedWork(title=best_title, catalog=best_catalog) if best_title else None

    async def _run_all(self, query: ResolverQuery) -> list[ResolverResult]:
        async def one(resolver: IComposerResolver) -> ResolverResult:
            try:
                return await resolver.resolve(query)
            except Exception as exc:  # noqa: BLE001
                return ResolverResult(provider=resolver.provider_id, candidates=(), error=str(exc))

        return list(await asyncio.gather(*(one(r) for r in self._resolvers)))

    def _flatten(self, results: list[ResolverResult]) -> list[WorkMatchPair]:
        out: list[WorkMatchPair] = []
        for result in results:
            for candidate in result.candidates:
                out.append((result.provider, candidate))
        return out

    def _merge(self, raw: list[WorkMatchPair]) -> list[ResolutionCandidate]:
        by_key: dict[str, list[tuple[str, ResolverCandidate]]] = {}
        for provider, candidate in raw:
            by_key.setdefault(_canonical_key(candidate.name), []).append((provider, candidate))

        out: list[ResolutionCandidate] = []
        for entries in by_key.values():
            names = [candidate.name for _, candidate in entries]
            display = self._display_name(names)
            aliases = tuple(
                sorted({name for name in names if name != display})
            )
            external: dict[str, str] = {}
            for _, candidate in entries:
                external.update(candidate.external_ids)
            providers: set[str] = set()
            for provider, _ in entries:
                providers.add(provider)
            confidence = sum(candidate.confidence for _, candidate in entries) / len(entries)
            out.append(
                ResolutionCandidate(
                    composer=ResolvedComposer(name=display, aliases=aliases, external_ids=external),
                    confidence=confidence,
                    providers=tuple(sorted(providers)),
                    evidence=tuple(
                        ResolutionEvidence(
                            provider=prov,
                            kind=e.kind,
                            confidence=e.confidence,
                            work_title=e.work_title,
                            work_catalog=e.work_catalog,
                        )
                        for prov, cand in entries
                        for e in cand.evidence
                    ),
                )
            )
        return out

    @staticmethod
    def _display_name(names: list[str]) -> str:
        for name in names:
            canonical = MetadataNormalizer.canonical_composer(name)
            if canonical and canonical != name:
                return canonical
        return names[0]

    @staticmethod
    def _collect_evidence(merged: list[ResolutionCandidate]) -> tuple[ResolutionEvidence, ...]:
        return tuple(e for candidate in merged for e in candidate.evidence)


def resolver_categories(resolvers: list[IComposerResolver]) -> frozenset[ResolverCategory]:
    out: set[ResolverCategory] = set()
    for resolver in resolvers:
        out.update(resolver.categories)
    return frozenset(out)
