"""V1 — Resolución de identidad de compositor (motor + endpoint)."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from src.osap.api.platform_app import create_platform_app
from src.osap.application.composer_resolution_engine import ComposerResolutionEngine
from src.osap.application.input_quality import classify_input_quality
from src.osap.application.use_cases.resolve_composer import ResolveComposerUseCase
from src.osap.bootstrap.container import Container
from src.osap.infrastructure.resolvers.canonical_resolver import CanonicalComposerResolver
from src.osap.ports.composer_resolver import (
    IComposerResolver,
    ResolverCandidate,
    ResolverCategory,
    ResolverEvidence,
    ResolverQuery,
    ResolverResult,
)


def test_input_quality_normal() -> None:
    assert classify_input_quality("Wolfgang Amadeus Mozart") == "normal"


def test_input_quality_suspicious() -> None:
    assert classify_input_quality("M") == "suspicious"


def test_input_quality_corrupt() -> None:
    assert classify_input_quality("ä æ R Z H çèª") == "corrupt_or_suspicious"
    assert classify_input_quality("\ufffd mozart") == "corrupt_or_suspicious"
    assert classify_input_quality("") == "corrupt_or_suspicious"


class _FakeResolver(IComposerResolver):
    def __init__(self, provider: str, name: str, confidence: float, *, category: ResolverCategory) -> None:
        self.provider_id = provider
        self._name = name
        self._confidence = confidence
        self.categories = frozenset({category})

    async def resolve(self, query: ResolverQuery) -> ResolverResult:
        candidate = ResolverCandidate(
            name=self._name,
            confidence=self._confidence,
            evidence=(ResolverEvidence(kind="work_match", confidence=self._confidence),),
        )
        return ResolverResult(provider=self.provider_id, candidates=(candidate,))


def _run(coro):
    return asyncio.run(coro)


def test_canonical_resolver_resolves_known() -> None:
    engine = ComposerResolutionEngine([CanonicalComposerResolver()])
    decision = _run(ResolveComposerUseCase(engine).execute("Mozart"))
    assert decision.status == "resolved"
    assert decision.composer is not None
    assert decision.composer.name == "Wolfgang Amadeus Mozart"
    assert decision.confidence == 0.9


def test_not_found_for_unknown() -> None:
    engine = ComposerResolutionEngine([CanonicalComposerResolver()])
    decision = _run(ResolveComposerUseCase(engine).execute("Some Unknown Composer Xyz"))
    assert decision.status == "not_found"
    assert decision.composer is None


def test_ambiguous_when_two_close_candidates() -> None:
    a = _FakeResolver("cpdl", "Wolfgang Amadeus Mozart", 0.6, category=ResolverCategory.CATALOG)
    b = _FakeResolver("wikidata", "Ludwig van Beethoven", 0.55, category=ResolverCategory.IDENTITY)
    engine = ComposerResolutionEngine([a, b])
    decision = _run(ResolveComposerUseCase(engine).execute("Mozart"))
    assert decision.status == "ambiguous"
    assert decision.composer is None
    assert len(decision.candidates) == 2


def test_resolved_merges_duplicate_candidates() -> None:
    a = _FakeResolver("cpdl", "Wolfgang Amadeus Mozart", 0.9, category=ResolverCategory.CATALOG)
    b = _FakeResolver("wikidata", "W. A. Mozart", 0.8, category=ResolverCategory.IDENTITY)
    engine = ComposerResolutionEngine([a, b])
    decision = _run(ResolveComposerUseCase(engine).execute("Mozart"))
    assert decision.status == "resolved"
    assert decision.composer is not None
    assert decision.composer.name == "Wolfgang Amadeus Mozart"
    assert decision.candidates[0].providers == ("cpdl", "wikidata")
    assert {e.provider for e in decision.evidence} == {"cpdl", "wikidata"}


def _fake_work_matcher(query: ResolverQuery) -> list[tuple[str, ResolverCandidate]]:
    # Simula la fase de obra: un catálogo encuentra la obra y asocia un compositor.
    candidate = ResolverCandidate(
        name="Xiao Youmei",
        confidence=0.95,
        evidence=(ResolverEvidence(kind="work_match", confidence=0.95, work_title=query.work_title),),
    )
    return [("imslp", candidate)]


def test_engine_resolves_via_work_when_composer_corrupt() -> None:
    engine = ComposerResolutionEngine([CanonicalComposerResolver()], work_matcher=_fake_work_matcher)
    decision = _run(
        ResolveComposerUseCase(engine).execute(
            composer="ä æ R Z H çèª",
            work_title="Song to the Auspicious Cloud - Second Version",
        )
    )
    assert decision.status == "resolved"
    assert decision.composer is not None
    assert decision.composer.name == "Xiao Youmei"
    providers = {e.provider for e in decision.evidence}
    assert "imslp" in providers


def test_wikidata_resolver_builds_identity() -> None:
    from src.osap.infrastructure.resolvers.wikidata_resolver import WikidataIdentityResolver

    resolver = WikidataIdentityResolver()

    async def run() -> ResolverResult:
        original = WikidataIdentityResolver._query
        WikidataIdentityResolver._query = staticmethod(
            lambda name: [
                {
                    "item": "Q53068",
                    "itemLabel": "Claudio Monteverdi",
                    "cpdlId": "794",
                    "mbid": "9a75168c-...",
                    "viaf": None,
                    "aliases": "Monteverdi|Monteverde",
                }
            ]
        )
        try:
            return await resolver.resolve(ResolverQuery(composer="Claudio Monteverdi"))
        finally:
            WikidataIdentityResolver._query = original

    result = asyncio.run(run())
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.name == "Claudio Monteverdi"
    assert "Monteverdi" in candidate.aliases
    assert candidate.external_ids["cpdl"] == "794"
    assert candidate.external_ids["musicbrainz"] == "9a75168c-..."


def _build_client(resolvers: list[IComposerResolver]) -> TestClient:
    container = Container()
    for resolver in resolvers:
        container.register_composer_resolver(resolver)
    return TestClient(create_platform_app(container=container))


def test_endpoint_resolved_known_composer() -> None:
    client = _build_client([CanonicalComposerResolver()])
    resp = client.post(
        "/api/v1/composers/resolve",
        json={"work": {"title": "Ave Verum Corpus"}, "composer": {"name": "Mozart"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["status"] == "resolved"
    assert data["composer"]["name"] == "Wolfgang Amadeus Mozart"
    assert data["input_quality"] == "normal"
    assert data["confidence"] == 0.9


def test_endpoint_not_found_and_quality() -> None:
    client = _build_client([CanonicalComposerResolver()])
    resp = client.post(
        "/api/v1/composers/resolve",
        json={
            "work": {"title": "Song to the Auspicious Cloud - Second Version"},
            "composer": {"name": "ä æ R Z H çèª"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "not_found"
    assert data["composer"] is None
    assert data["input_quality"] == "corrupt_or_suspicious"
    assert data["evidence"] == []


def test_endpoint_work_only_no_composer() -> None:
    client = _build_client([CanonicalComposerResolver()])
    resp = client.post(
        "/api/v1/composers/resolve",
        json={"work": {"title": "Some Work Title"}},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "not_found"
    assert data["composer"] is None
    assert data["input_quality"] == "normal"


def test_endpoint_requires_work_title() -> None:
    client = _build_client([CanonicalComposerResolver()])
    resp = client.post("/api/v1/composers/resolve", json={"composer": {"name": "Mozart"}})
    assert resp.status_code == 422
