"""Generic ICatalogProvider adapter built on the Provider layer (Provider API v1.3).

A provider is described by declarative YAML (provider.yaml, endpoints.yaml, mapping.yaml,
resources.yaml) plus an optional Level-2 `ProviderFetcher` that translates a non-REST
protocol (MediaWiki, GitHub, ...) into normalized contract JSON. The adapter never
downloads files: it only maps provider JSON into OSAP internal objects. Download is
handled by OSAP-API via the resource links.
"""

from dataclasses import replace
from pathlib import Path

from src.osap.domain.acquisition_result import AcquisitionResult
from src.osap.domain.candidate_representation import CandidateRepresentation
from src.osap.domain.catalog_capabilities import CatalogCapabilities
from src.osap.domain.catalog_info import CatalogInfo
from src.osap.domain.catalog_status import CatalogStatus
from src.osap.domain.output_format import OutputFormat
from src.osap.domain.resolve_request import ResolveRequest
from src.osap.domain.search_request import SearchRequest
from src.osap.domain.value_objects import CandidateId, CatalogId, Confidence, ProviderId, WorkId
from src.osap.domain.work_descriptor import WorkDescriptor
from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    GenericProviderAdapter,
    ProviderDefinition,
    ProviderFetcher,
    ProviderQuery,
    load_definition,
)
from src.osap.infrastructure.providers.contracts import ProviderResource, ProviderWork
from src.osap.ports.catalog_provider import ICatalogProvider

_PROVIDERS_ROOT = Path(__file__).resolve().parents[5] / "providers"

_FORMATS = {
    "musicxml": OutputFormat.MUSICXML,
    "pdf": OutputFormat.PDF,
    "midi": OutputFormat.MIDI,
    "mei": OutputFormat.MEI,
}


def _format(value: str) -> OutputFormat:
    return _FORMATS.get(value.lower(), OutputFormat.MUSICXML)


class RemoteCatalogProvider(ICatalogProvider):
    """Any YAML-declared provider, driven entirely by its definition + optional fetcher.

    Level 1 (REST): only the definition, the adapter performs HTTP.
    Level 2 (MediaWiki/GitHub/...): a `ProviderFetcher` supplies normalized JSON that
    flows through the same mapping.
    """

    def __init__(
        self,
        definition: ProviderDefinition | None = None,
        definition_path: Path | None = None,
        fetcher: ProviderFetcher | None = None,
        base_url: str | None = None,
    ) -> None:
        self._definition = definition or load_definition(definition_path or _PROVIDERS_ROOT / "omr")
        if base_url:
            # Allow switching the operator endpoint without touching the YAML definition
            # (e.g. a local osap-storage in dev vs. the remote storage.openmusicrepository.com).
            self._definition = replace(self._definition, base_url=base_url.rstrip("/"))
        self._fetcher = fetcher
        self._adapter = GenericProviderAdapter(self._definition, fetcher=fetcher)

    @property
    def provider_id(self) -> ProviderId:
        return ProviderId(self._definition.id)

    def search(self, request: SearchRequest) -> tuple[CandidateRepresentation, ...]:
        query = ProviderQuery(
            query=request.query or "",
            composer=request.composer,
            catalogue=getattr(request, "catalogue", None),
            title=request.title,
            limit=100,
        )
        works = self._adapter.search(query)
        candidates: list[CandidateRepresentation] = []
        index = 0
        for work in works:
            for resource in work.resources:
                candidates.append(self._candidate(index, work, resource))
                index += 1
        return tuple(candidates)

    def _candidate(self, index: int, work: ProviderWork, resource: ProviderResource) -> CandidateRepresentation:
        identity = work.identity
        return CandidateRepresentation(
            candidate_id=CandidateId(f"{self._definition.id}-{index}"),
            work_descriptor=WorkDescriptor(
                WorkId(identity.id),
                identity.title,
                composer=identity.composer,
                catalogue_number=identity.catalogue,
            ),
            provider_id=self.provider_id,
            format=_format(resource.format),
            confidence=Confidence(identity.confidence),
            remote_id=resource.id,
            download_url=resource.links.download,
            public_domain=work.metadata.public_domain,
            license=work.metadata.license,
        )

    def resolve(self, request: ResolveRequest) -> CandidateRepresentation | None:
        candidates = self.search(SearchRequest.from_resolve(request))
        return candidates[0] if candidates else None

    def download(
        self, candidate: CandidateRepresentation, output_format: OutputFormat | None = None
    ) -> AcquisitionResult:
        raise NotImplementedError("Download is provided by osap-api via the provider's links")

    def metadata(self) -> CatalogInfo:
        return CatalogInfo(
            CatalogId(self._definition.id),
            self._definition.name,
            self.provider_id,
            "remote",
            CatalogStatus.AVAILABLE,
        )

    def capabilities(self) -> CatalogCapabilities:
        return CatalogCapabilities(
            self.provider_id,
            formats=(OutputFormat.MUSICXML, OutputFormat.PDF, OutputFormat.MIDI),
        )
