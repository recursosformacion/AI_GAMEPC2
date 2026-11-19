"""Utilidades IIIF: validar manifiestos y registrarlos como fuente de una obra."""

from __future__ import annotations

from typing import Any, cast

import requests

from src.osap.application.enrichment.models import EnrichmentCandidate


def looks_like_iiif_manifest(payload: dict[str, Any]) -> bool:
    """True si el JSON parece un manifiesto IIIF Presentation (v2 o v3)."""
    type_value = payload.get("@type") or payload.get("type")
    if isinstance(type_value, str) and "Manifest" in type_value:
        return True
    context = payload.get("@context")
    values = context if isinstance(context, list) else [context]
    return any("iiif.io/api/presentation" in str(item) for item in values)


def fetch_manifest(session: Any, url: str, timeout: int = 30) -> dict[str, Any] | None:
    headers = {"Accept": "application/json", "User-Agent": "OSAP-Enrichment/0.1"}
    response = session.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return cast("dict[str, Any]", payload) if isinstance(payload, dict) else None


def manifest_candidate(entity_key: str, url: str, payload: dict[str, Any]) -> EnrichmentCandidate:
    """Candidato que enlaza un manifiesto IIIF como fuente de la obra (staging)."""
    confidence = 0.9 if looks_like_iiif_manifest(payload) else 0.5
    return EnrichmentCandidate(
        entity_type="work",
        entity_key=entity_key,
        field="iiif_manifest",
        value=url,
        source="iiif",
        evidence_url=url,
        confidence=confidence,
        license="institution-terms",
    )


def default_session() -> Any:
    return requests.Session()
