"""F3 (ADR-0035) — adaptador sesión→dominio y acquirers sin pérdida.

Cubre el mapeo ProviderWork → CandidateRepresentation (domain_adapter), la vía de
reanudación JSON → ProviderWork, y que CatalogAcquirer/ProviderAdapterAcquirer adjuntan
los objetos de dominio vivos en AcquiredPage.candidates.
"""

import json

from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.quality_level import QualityLevel
from src.osap.domain.value_objects import CandidateId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.providers.contracts import (
    ProviderIdentity,
    ProviderLinks,
    ProviderMetadata,
    ProviderResource,
    ProviderWork,
)
from src.osap.infrastructure.resolution.domain_adapter import (
    provider_work_to_candidate,
    provider_works_to_candidates,
)
from src.osap.infrastructure.resolution.provider_acquirer import (
    CatalogAcquirer,
    ProviderAdapterAcquirer,
    provider_work_to_dict,
    provider_works_from_json,
)


def _work(
    *,
    composer: str | None = "Mozart",
    resources: tuple[ProviderResource, ...] = (),
    confidence: float = 0.9,
) -> ProviderWork:
    return ProviderWork(
        identity=ProviderIdentity(
            id="omr-1",
            title="Ave Verum Corpus",
            composer=composer,
            catalogue="KV 618",
            confidence=confidence,
        ),
        metadata=ProviderMetadata(
            musical_key="C",
            license="CC BY",
            public_domain=True,
            genres=("motet",),
        ),
        resources=resources,
    )


def _resource(format: str = "musicxml", download: str | None = "https://cdn/x.musicxml") -> ProviderResource:
    return ProviderResource(
        id="res-1",
        format=format,
        license="CC BY",
        links=ProviderLinks(download=download, view="https://view"),
    )


def test_full_mapping_keeps_identity_and_resource() -> None:
    candidate = provider_work_to_candidate(
        "omr", _work(resources=(_resource("pdf"), _resource("musicxml")))
    )
    work = candidate.work_descriptor
    assert work.title == "Ave Verum Corpus"
    assert work.composer == "Mozart"
    assert work.catalogue_number == "KV 618"
    assert work.work_id == WorkId("omr-1")
    assert work.genres == ("motet",)
    assert candidate.provider_id == ProviderId("omr")
    assert candidate.candidate_id == CandidateId("omr:res-1")
    assert candidate.remote_id == "omr-1"
    assert candidate.format == OutputFormat.MUSICXML  # mejor recurso (no PDF)
    assert candidate.downloadable is True
    assert candidate.download_url == "https://cdn/x.musicxml"
    assert candidate.public_domain is True
    assert candidate.confidence == Confidence(0.9)


def test_no_resources_keeps_evidence_but_not_downloadable() -> None:
    candidate = provider_work_to_candidate("omr", _work(resources=()))
    assert candidate.work_descriptor.title == "Ave Verum Corpus"
    assert candidate.downloadable is False
    assert candidate.download_url is None
    assert candidate.format == OutputFormat.PDF


def test_unknown_composer_is_not_invented() -> None:
    candidate = provider_work_to_candidate("omr", _work(composer=None))
    assert candidate.work_descriptor.composer is None


def test_adapter_never_invents_quality_or_checksum() -> None:
    candidate = provider_work_to_candidate("omr", _work(resources=(_resource(),)))
    assert candidate.quality is QualityLevel.UNREADABLE
    assert candidate.completeness == 1.0
    assert candidate.checksum is None


def test_json_roundtrip_restores_identity_and_resource() -> None:
    original = _work(resources=(_resource(),))
    restored = provider_works_from_json(json.dumps([provider_work_to_dict(original)]))
    assert len(restored) == 1
    candidate = provider_work_to_candidate("omr", restored[0])
    assert candidate.work_descriptor.title == "Ave Verum Corpus"
    assert candidate.work_descriptor.composer == "Mozart"
    assert candidate.work_descriptor.catalogue_number == "KV 618"
    assert candidate.format == OutputFormat.MUSICXML
    assert candidate.license == "CC BY"
    # Subconjunto documentado: quality/completeness no viajan en JSON.
    assert candidate.quality is QualityLevel.UNREADABLE
    assert candidate.completeness == 1.0


def test_catalog_acquirer_attaches_live_candidates() -> None:
    candidate = CandidateRepresentation(
        candidate_id=CandidateId("c1"),
        work_descriptor=WorkDescriptor(work_id=WorkId("w1"), title="Ave Verum", composer="Mozart"),
        provider_id=ProviderId("fake"),
        format=OutputFormat.MUSICXML,
        confidence=Confidence(0.9),
    )

    class _StubProvider:
        def search(self, request: object) -> tuple[CandidateRepresentation, ...]:
            return (candidate,)

    page = CatalogAcquirer("fake", _StubProvider()).acquire_page("fake", "1", "Ave Verum")
    assert page.candidates == (candidate,)
    assert len(page.works) == 1
    assert page.works[0].identity.title == "Ave Verum"
    assert page.works[0].identity.composer == "Mozart"


def test_provider_adapter_acquirer_attaches_domain_candidates() -> None:
    work = _work(resources=(_resource(),))

    class _StubAdapter:
        def search(self, query: object) -> tuple[ProviderWork, ...]:
            return (work,)

    page = ProviderAdapterAcquirer("omr", _StubAdapter()).acquire_page("omr", "1", "Ave Verum")
    assert len(page.candidates) == 1
    assert page.works == (work,)
    candidate = page.candidates[0]
    assert candidate.provider_id == ProviderId("omr")
    assert candidate.work_descriptor.title == "Ave Verum Corpus"


def test_batch_conversion() -> None:
    works = (_work(resources=(_resource(),)), _work(resources=()))
    candidates = provider_works_to_candidates("omr", works)
    assert len(candidates) == 2
    assert candidates[0].candidate_id != candidates[1].candidate_id
