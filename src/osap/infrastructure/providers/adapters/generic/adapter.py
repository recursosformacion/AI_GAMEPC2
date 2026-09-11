"""ProviderFetcher + GenericProviderAdapter (orquestación HTTP+mapping)."""

from __future__ import annotations

import logging

from src.osap.infrastructure.providers.contracts import (
    ProviderIdentity,
    ProviderResource,
    ProviderStatistics,
    ProviderWork,
)

from .mapping import (
    _apply_mapping,
    _apply_transform,
    _as_opt_float,
    _as_opt_int,
    _as_opt_str,
    _build_metadata,
    _build_resource,
    _first_list,
    _resolve_query,
)
from .models import Endpoint, ProviderDefinition, ProviderHttpClient, ProviderQuery

_LOGGER = logging.getLogger("osap.providers.generic")


class ProviderFetcher:
    """Level-2 protocol adapter.

    Talks to a non-REST source (MediaWiki, GitHub, ...) and returns JSON equivalent to
    the provider contract. The result flows through the same mapping pipeline as any
    Level-1 REST provider. This keeps ~95% of the code common: only authentication,
    URL generation and small protocol transforms live here.
    """

    def fetch(
        self, definition: ProviderDefinition, endpoint: Endpoint, query: ProviderQuery
    ) -> dict[str, object] | None:
        """Return a dict whose list items map through `definition.work_mapping`."""
        return None

    def fetch_resource(
        self, definition: ProviderDefinition, endpoint: Endpoint, work_id: str
    ) -> dict[str, object] | None:
        """Return a single-work dict for direct access by id."""
        return None


class GenericProviderAdapter:
    """Reads a ProviderDefinition, obtains normalized JSON, applies mappings and
    yields `ProviderWork`.

    Level 1 providers (pure REST) use the default HTTP fetcher and the endpoints in the
    definition. Level 2 providers (MediaWiki, GitHub, ...) supply a custom ``fetcher``
    that talks to the source and returns JSON equivalent to the provider contract; that
    JSON then flows through the exact same mapping pipeline. There is no N+1: a single
    call maps each fully-populated Work into `ProviderWork`.
    """

    def __init__(
        self,
        definition: ProviderDefinition,
        http: ProviderHttpClient | None = None,
        fetcher: ProviderFetcher | None = None,
    ) -> None:
        self._definition = definition
        self._http = http or ProviderHttpClient(definition.base_url, "application/vnd.osap-api.v1.3+json")
        self._fetcher = fetcher

    def search(self, query: ProviderQuery) -> tuple[ProviderWork, ...]:
        search = self._definition.endpoints.get("search")
        if search is None:
            return ()
        data = self._fetch(search, query)
        if not data:
            return ()
        works = _first_list(data, "works", "results", "data")
        return self._map_works(works)

    def lookup(self, query: str) -> tuple[ProviderWork, ...]:
        """Lightweight autocomplete: maps `/api/lookup` results directly (no resolution).

        Returns only Identity-bearing `ProviderWork` (id, title, composer, catalogue).
        Never used in the resolution pipeline.
        """
        lookup = self._definition.endpoints.get("lookup")
        if lookup is None:
            return ()
        data = self._fetch(lookup, ProviderQuery(query=query))
        if not data:
            return ()
        results = _first_list(data, "results", "works", "data")
        return self._map_works(results)

    def resource(self, work_id: str) -> ProviderWork | None:
        """Direct access to a known Work by id. Not part of the search pipeline."""
        resource = self._definition.endpoints.get("resource")
        if resource is None:
            return None
        data = self._fetch_resource(resource, work_id)
        if not data:
            return None
        values = _apply_mapping(data, self._definition.work_mapping)
        return self._build_work(data, values)

    def _fetch(self, endpoint: Endpoint, query: ProviderQuery) -> dict[str, object] | None:
        if self._fetcher is not None:
            return self._fetcher.fetch(self._definition, endpoint, query)
        params = self._params_for(endpoint, query)
        return self._http.get(endpoint.path, params)

    def _fetch_resource(self, endpoint: Endpoint, work_id: str) -> dict[str, object] | None:
        if self._fetcher is not None:
            return self._fetcher.fetch_resource(self._definition, endpoint, work_id)
        path = endpoint.path.format(id=work_id)
        return self._http.get(path)

    def _params_for(self, endpoint: Endpoint, query: ProviderQuery) -> dict[str, object]:
        if endpoint.query:
            return _resolve_query(endpoint.query, query)
        params: dict[str, object] = {}
        fields = {
            "query": query.query,
            "composer": query.composer,
            "catalogue": query.catalogue,
            "title": query.title,
            "page": query.page,
            "limit": query.limit,
        }
        for osap_field, value in fields.items():
            if value is None:
                continue
            provider_param = self._definition.request_mapping.get(osap_field)
            if provider_param:
                params[provider_param] = value
        return params

    def _map_works(self, works: object) -> tuple[ProviderWork, ...]:
        if not isinstance(works, list):
            return ()
        result: list[ProviderWork] = []
        for item in works:
            if not isinstance(item, dict):
                continue
            values = _apply_mapping(item, self._definition.work_mapping)
            result.append(self._build_work(item, values))
        return tuple(result)

    def _build_work(self, doc: dict[str, object], values: dict[str, object]) -> ProviderWork:
        values = self._apply_transforms(values, "fields")
        identity = ProviderIdentity(
            id=str(values.get("id") or "unknown"),
            title=str(values.get("title") or "Unknown"),
            composer=_as_opt_str(values.get("composer")),
            catalogue=_as_opt_str(values.get("catalogue")),
            confidence=_as_opt_float(values.get("confidence")) or 0.9,
        )
        metadata = _build_metadata(values)
        statistics = ProviderStatistics(
            favorites=_as_opt_int(values.get("favorites")) or 0,
            downloads=_as_opt_int(values.get("downloads")) or 0,
            views=_as_opt_int(values.get("views")) or 0,
            rating=_as_opt_float(values.get("rating")) or 0.0,
        )
        resources = self._resources(doc.get(self._definition.resource_list))
        return ProviderWork(identity=identity, metadata=metadata, statistics=statistics, resources=resources)

    def _resources(self, raw: object) -> tuple[ProviderResource, ...]:
        if not isinstance(raw, list):
            return ()
        out: list[ProviderResource] = []
        for item in raw:
            if isinstance(item, dict):
                mapped = _apply_mapping(item, self._definition.resource_mapping)
                mapped = self._apply_transforms(mapped, "resources")
                out.append(_build_resource(mapped, self._definition.base_url))
        return tuple(out)

    def _apply_transforms(self, values: dict[str, object], section: str) -> dict[str, object]:
        """Apply the declared `transforms.yaml` operations to mapped fields."""
        transforms = self._definition.transforms.get(section)
        if not isinstance(transforms, dict):
            return values
        out = dict(values)
        for key, ops in transforms.items():
            if key in out:
                out[key] = _apply_transform(out[key], ops)
        return out


