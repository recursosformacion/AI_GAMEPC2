"""Carga de definiciones YAML de proveedores y de configuraciones."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import yaml  # type: ignore[import-untyped]

from .models import Endpoint, ProviderDefinition

if TYPE_CHECKING:
    from pathlib import Path

_LOGGER = logging.getLogger("osap.providers.generic")


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
        transforms=_load_transforms(path / "transforms.yaml"),
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
        transforms=_normalize_transforms(doc.get("transforms")),
    )


def _load_transforms(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _normalize_transforms(doc)


def _normalize_transforms(doc: object) -> dict[str, object]:
    """Keep only the `fields:` / `resources:` transform sections (ignore comments/keys)."""
    if not isinstance(doc, dict):
        return {}
    out: dict[str, object] = {}
    for section in ("fields", "resources"):
        block = doc.get(section)
        if isinstance(block, dict):
            out[section] = {str(k): v for k, v in block.items()}
    return out


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


def load_definition_from_config(provider_id: str, config: dict[str, object]) -> ProviderDefinition:
    """Reconstruye una `ProviderDefinition` desde el config JSON persistido en la BD.

    El config es la representación de los ficheros YAML de un proveedor:
    {"provider": {...}, "endpoints": {...}, "mapping": {...}, "resources": {...}, "transforms": {...}}.
    """
    provider = config.get("provider")
    provider_doc = provider if isinstance(provider, dict) else {}
    endpoints_doc = config.get("endpoints")
    endpoints = _parse_endpoints(endpoints_doc if isinstance(endpoints_doc, dict) else {})

    mapping_doc = config.get("mapping")
    mapping = mapping_doc if isinstance(mapping_doc, dict) else {}
    work_block = mapping.get("works") or mapping.get("work") or {}
    work, resource_mapping, resource_list = _split_work_mapping(work_block)

    resources_doc = config.get("resources")
    if isinstance(resources_doc, dict):
        res_block = resources_doc.get("works") or resources_doc.get("work") or {}
        extra_work, extra_mapping, extra_list = _split_work_mapping(res_block)
        if extra_mapping:
            resource_mapping = {**resource_mapping, **extra_mapping}
        if extra_list:
            resource_list = extra_list

    transforms_doc = config.get("transforms")
    transforms = _normalize_transforms(transforms_doc)

    return ProviderDefinition(
        id=str(provider_doc.get("id") or provider_id),
        name=str(provider_doc.get("name") or provider_doc.get("id") or provider_id),
        base_url=str(provider_doc.get("base_url") or ""),
        endpoints=endpoints,
        work_mapping=work,
        resource_list=resource_list,
        resource_mapping=resource_mapping,
        authentication=_auth_type(provider_doc.get("authentication")),
        transforms=transforms,
    )


def _flatten_work_mapping(dotted: dict[str, str]) -> dict[str, str]:
    """Convert legacy dotted-target mapping (`identity.id` -> source) to flat keys
    (`id` -> source) used by `_build_work`."""
    flat: dict[str, str] = {}
    for target, source in dotted.items():
        parts = target.split(".", 1)
        key = parts[-1]
        flat[key] = source
    return flat
