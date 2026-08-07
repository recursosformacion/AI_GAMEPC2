"""Generic Provider Adapter (Provider API v1.3).

A provider is described entirely by declarative YAML files (provider.yaml, endpoints.yaml,
mapping.yaml). The adapter performs HTTP, applies the mappings, and produces `ProviderWork`
— the single DTO all providers return.

Contract v1.3: `/api/search` returns a collection of fully-populated Works
(Identity + Metadata + Statistics + Resources) in a single call. The adapter maps each
Work directly into `ProviderWork`. It performs NO additional HTTP calls during search
(there is no N+1, no `resource(id)` in the resolution pipeline).

`resource/{id}` exists only as an optional direct-access service for known ids and is
never called during search. `lookup` is reserved for lightweight/autocomplete queries
and is also outside the resolution pipeline.
"""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from src.osap.infrastructure.providers.contracts import (
    ProviderIdentity,
    ProviderLinks,
    ProviderMetadata,
    ProviderResource,
    ProviderStatistics,
    ProviderWork,
)


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    name: str
    base_url: str
    endpoints: dict[str, Endpoint]
    work_mapping: dict[str, str]
    resource_mapping: dict[str, str]
    resource_list: str = "resources"
    request_mapping: dict[str, str] = field(default_factory=dict)
    authentication: str | None = None


@dataclass
class ProviderQuery:
    query: str = ""
    composer: str | None = None
    catalogue: str | None = None
    title: str | None = None
    page: int = 1
    limit: int = 50


class ProviderHttpClient:
    def __init__(self, base_url: str, accept: str) -> None:
        self._base_url = base_url
        self._accept = accept

    def get(self, path: str, params: dict[str, object] | None = None) -> dict[str, object] | None:
        url = self._base_url + path
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"Accept": self._accept, "User-Agent": "Mozilla/5.0 (OSAP provider adapter)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (provider endpoint)
                data = json.loads(resp.read())
        except Exception:
            return None
        return data if isinstance(data, dict) else None


def _get_path(doc: object, dotted: str) -> object:
    cur: object = doc
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _apply_mapping(doc: object, mapping: dict[str, str]) -> dict[str, object]:
    out: dict[str, object] = {}
    for target, source in mapping.items():
        value = _get_path(doc, source)
        if value is not None:
            out[target] = value
    return out


def _as_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(v) for v in value)


def _as_opt_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _as_opt_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _as_opt_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _as_opt_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def _build_metadata(values: dict[str, object]) -> ProviderMetadata:
    return ProviderMetadata(
        subtitle=_as_opt_str(values.get("subtitle")),
        opus=_as_opt_str(values.get("opus")),
        musical_key=_as_opt_str(values.get("musical_key")),
        duration=_as_opt_str(values.get("duration")),
        measures=_as_opt_int(values.get("measures")),
        pages=_as_opt_int(values.get("pages")),
        parts=_as_opt_int(values.get("parts")),
        license=_as_opt_str(values.get("license")),
        public_domain=_as_opt_bool(values.get("public_domain")),
        description=_as_opt_str(values.get("description")),
        genres=_as_strings(values.get("genres")),
        tags=_as_strings(values.get("tags")),
        instruments=_as_strings(values.get("instruments")),
        parts_names=_as_strings(values.get("parts_names")),
    )


def _build_resource(values: dict[str, object], base_url: str) -> ProviderResource:
    return ProviderResource(
        id=str(values.get("id") or ""),
        format=str(values.get("format") or ""),
        mime_type=_as_opt_str(values.get("mime_type")),
        available=bool(values.get("available", True)),
        license=_as_opt_str(values.get("license")),
        links=ProviderLinks(
            download=_resolve_url(base_url, _as_opt_str(values.get("links.download"))),
            view=_resolve_url(base_url, _as_opt_str(values.get("links.view"))),
            thumbnail=_resolve_url(base_url, _as_opt_str(values.get("links.thumbnail"))),
        ),
    )


def _resolve_url(base_url: str, value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith(("http://", "https://", "//")):
        return value
    return (base_url.rstrip("/") + "/" + value.lstrip("/")) if base_url else value


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
        fetcher: "ProviderFetcher | None" = None,
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
                out.append(_build_resource(mapped, self._definition.base_url))
        return tuple(out)


def _resolve_query(template: dict[str, str], query: ProviderQuery) -> dict[str, object]:
    values = {
        "query": query.query,
        "composer": query.composer,
        "catalogue": query.catalogue,
        "title": query.title,
        "page": query.page,
        "limit": query.limit,
    }
    params: dict[str, object] = {}
    for key, raw in template.items():
        name = raw.strip("{}").strip()
        value = values.get(name)
        if value is None:
            continue
        params[key] = value
    return params


def _first_list(doc: dict[str, object], *keys: str) -> object:
    for key in keys:
        value = doc.get(key)
        if isinstance(value, list):
            return value
    return None


def load_definition(path: Path) -> ProviderDefinition:
    """Load a `ProviderDefinition` from a directory of YAML files or a single YAML file.

    Directory layout:
      - provider.yaml    -> id, name, base_url, authentication, contract
      - endpoints.yaml   -> endpoint blocks (method, path, query templates)
      - mapping.yaml     -> `work:` block (flat targets, `array`, `fields`, `links`)
      - resources.yaml   -> (optional) alternative location for the resource mapping
    """
    if path.is_dir():
        return _load_definition_dir(path)
    return _load_definition_file(path)


def _load_definition_dir(path: Path) -> ProviderDefinition:
    provider = yaml.safe_load((path / "provider.yaml").read_text(encoding="utf-8")) or {}
    endpoints_doc = yaml.safe_load((path / "endpoints.yaml").read_text(encoding="utf-8")) or {}
    mapping_doc = yaml.safe_load((path / "mapping.yaml").read_text(encoding="utf-8")) or {}
    work_block = mapping_doc.get("works") or mapping_doc.get("work") or {}
    work, resource_mapping, resource_list = _split_work_mapping(work_block)
    resources_path = path / "resources.yaml"
    if resources_path.exists():
        resources_doc = yaml.safe_load(resources_path.read_text(encoding="utf-8")) or {}
        res_block = resources_doc.get("works") or resources_doc.get("work") or {}
        extra_work, extra_mapping, extra_list = _split_work_mapping(res_block)
        if extra_mapping:
            resource_mapping = {**resource_mapping, **extra_mapping}
        if extra_list:
            resource_list = extra_list
    endpoints = _parse_endpoints(endpoints_doc)
    return ProviderDefinition(
        id=str(provider.get("id") or "provider"),
        name=str(provider.get("name") or provider.get("id") or "provider"),
        base_url=str(provider.get("base_url") or ""),
        endpoints=endpoints,
        work_mapping=work,
        resource_list=resource_list,
        resource_mapping=resource_mapping,
        authentication=_auth_type(provider.get("authentication")),
    )


def _load_definition_file(path: Path) -> ProviderDefinition:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    endpoints = _parse_endpoints(doc.get("endpoints") or {})
    response_mapping = dict(doc.get("response_mapping") or {})
    work_mapping = _flatten_work_mapping(response_mapping)
    return ProviderDefinition(
        id=str(doc.get("id") or doc.get("name") or "provider"),
        name=str(doc.get("name") or doc.get("id") or "provider"),
        base_url=str(doc.get("base_url") or ""),
        endpoints=endpoints,
        work_mapping=work_mapping,
        resource_list=str(doc.get("resource_list") or "resources"),
        resource_mapping=dict(doc.get("resource_mapping") or {}),
        request_mapping=dict(doc.get("request_mapping") or {}),
        authentication=_auth_type(doc.get("authentication")),
    )


def _parse_endpoints(endpoints_doc: dict[str, object]) -> dict[str, Endpoint]:
    out: dict[str, Endpoint] = {}
    for name, raw in endpoints_doc.items():
        if not isinstance(raw, dict):
            continue
        query_raw = raw.get("query")
        query = {k: str(v) for k, v in query_raw.items()} if isinstance(query_raw, dict) else {}
        out[name] = Endpoint(method=str(raw.get("method") or "GET"), path=str(raw.get("path") or ""), query=query)
    return out


def _split_work_mapping(
    work: dict[str, object],
) -> tuple[dict[str, str], dict[str, str], str]:
    """Separate the `work` block into flat field mapping, resource mapping and array key.

    `array` -> the response key holding the resource list.
    `fields` -> per-resource field mapping.
    `links` -> per-resource link mapping (prefixed with `links.`).
    All other keys -> flat `ProviderWork` field mapping.
    """
    flat: dict[str, str] = {}
    resource_fields: dict[str, str] = {}
    resource_links: dict[str, str] = {}
    resource_list = "resources"
    for target, source in work.items():
        if target == "array":
            resource_list = str(source or "resources")
        elif target == "fields" and isinstance(source, dict):
            resource_fields.update({str(k): str(v) for k, v in source.items()})
        elif target == "links" and isinstance(source, dict):
            resource_links.update({f"links.{k}": str(v) for k, v in source.items()})
        elif source is None:
            continue
        else:
            flat[str(target)] = str(source)
    resource_mapping = {**resource_fields, **resource_links}
    return flat, resource_mapping, resource_list


def _auth_type(auth: object) -> str | None:
    if isinstance(auth, dict):
        value = auth.get("type")
        return str(value) if value else None
    if auth is None:
        return None
    return str(auth)


def _flatten_work_mapping(dotted: dict[str, str]) -> dict[str, str]:
    """Convert legacy dotted-target mapping (`identity.id` -> source) to flat keys
    (`id` -> source) used by `_build_work`."""
    flat: dict[str, str] = {}
    for target, source in dotted.items():
        parts = target.split(".", 1)
        key = parts[-1]
        flat[key] = source
    return flat
