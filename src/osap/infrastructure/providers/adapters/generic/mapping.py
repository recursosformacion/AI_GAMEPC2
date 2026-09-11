"""Mapeo/transformación genérica de respuestas a objetos v1.3."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from src.osap.infrastructure.providers.contracts import (
    ProviderLinks,
    ProviderMetadata,
    ProviderResource,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from .models import ProviderQuery

_LOGGER = logging.getLogger("osap.providers.generic")


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


def _strip_parenthetical(value: object) -> object:
    if not isinstance(value, str):
        return value
    return re.sub(r"\s*\([^)]*\)", "", value).strip()


_SIMPLE_TRANSFORMS: dict[str, Callable[[object], object]] = {
    "trim": lambda v: v.strip() if isinstance(v, str) else v,
    "lower": lambda v: v.lower() if isinstance(v, str) else v,
    "upper": lambda v: v.upper() if isinstance(v, str) else v,
    "empty_to_null": lambda v: (None if v in ("", "None", "null") else v),
    "strip_parenthetical": _strip_parenthetical,
}


def _apply_transform(value: object, ops: object) -> object:
    """Apply a single transform op or a list of ops (in order) to a mapped value."""
    if not isinstance(ops, list):
        ops = [ops]
    for op in ops:
        if isinstance(op, str):
            fn = _SIMPLE_TRANSFORMS.get(op)
            if fn is not None:
                value = fn(value)
        elif isinstance(op, dict):
            kind = op.get("type")
            if kind == "regex" and isinstance(value, str):
                value = re.sub(str(op.get("pattern", "")), str(op.get("replace", "")), value)
            else:
                fn = _SIMPLE_TRANSFORMS.get(str(kind))
                if fn is not None:
                    value = fn(value)
    return value


