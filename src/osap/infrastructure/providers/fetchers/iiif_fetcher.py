"""Level-2 protocol adapter for IIIF Manifest providers (BNE, BnF, LoC, DIAMM, HathiTrust).

Talks to IIIF Presentation API 3.0 endpoints and returns JSON equivalent to the
provider contract (`works` -> list of Work dicts). The result flows through the
same mapping pipeline as any Level-1 REST provider. Only IIIF-specific logic
(manifest traversal, canvas extraction, metadata parsing) lives here.
"""

import json
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import urljoin

from src.osap.infrastructure.providers.adapters.generic_provider_adapter import (
    Endpoint,
    ProviderDefinition,
    ProviderFetcher,
    ProviderQuery,
)


class IIIFFetcher(ProviderFetcher):
    """IIIF Presentation API -> normalized contract JSON."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {
            "Accept": "application/ld+json, application/json",
            "User-Agent": "Mozilla/5.0 (OSAP IIIF fetcher)",
        }

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """HTTP GET with urllib, returns parsed JSON or None on error."""
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, method="GET", headers=self._headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                data = json.loads(resp.read())
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def fetch(
        self, definition: ProviderDefinition, endpoint: Endpoint, query: ProviderQuery
    ) -> dict[str, Any] | None:
        """Search via IIIF Search API or OAI-PMH; fallback to manifest list."""
        search_path = endpoint.path.format(
            query=query.query or "",
            page=query.page or 1,
            limit=query.limit or 50,
        )
        url = urljoin(self._base_url + "/", search_path.lstrip("/"))

        data = self._get(url, params={"format": "json"})
        if not data:
            return {"works": []}

        # IIIF Search API returns { "items": [ { "id": "...", "label": {...}, "metadata": [...] } ] }
        # OAI-PMH returns different structure; we normalize both to {"works": [...]}
        works = self._normalize_search_response(data)
        return {"works": works}

    def fetch_resource(
        self, definition: ProviderDefinition, endpoint: Endpoint, work_id: str
    ) -> dict[str, Any] | None:
        """Fetch a single IIIF Manifest by ID."""
        url = urljoin(self._base_url + "/", f"manifests/{work_id}")
        return self._get(url)

    def _normalize_search_response(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize IIIF Search / OAI-PMH / Manifest List responses to works list."""
        works: list[dict[str, Any]] = []

        # IIIF Search API 1.0/2.0: { "items": [ { "id": "...", "label": {...}, "metadata": [...] } ] }
        if isinstance(data.get("items"), list):
            for item in data["items"]:
                works.append(self._item_to_work(item))
            return works

        # OAI-PMH ListRecords: { "ListRecords": { "record": [ { "metadata": {...} } ] } }
        if "ListRecords" in data:
            records = data["ListRecords"].get("record", [])
            if not isinstance(records, list):
                records = [records]
            for rec in records:
                md = rec.get("metadata", {})
                works.append(self._oai_to_work(md, rec.get("header", {}).get("identifier")))
            return works

        # Direct manifest list: { "manifests": [ {...} ] }
        if isinstance(data.get("manifests"), list):
            for m in data["manifests"]:
                works.append(self._manifest_to_work(m))
            return works

        return works

    def _item_to_work(self, item: dict[str, Any]) -> dict[str, Any]:
        """Convert IIIF Search item to work dict."""
        # label: { "en": ["Title"] } or { "none": ["Title"] }
        label = item.get("label", {})
        title = self._first_label(label)

        # metadata: [ { "label": { "en": ["Composer"] }, "value": { "en": ["Bach"] } } ]
        metadata = {m.get("label", {}).get("en", [""])[0]: m.get("value", {}).get("en", [""])[0]
                    for m in item.get("metadata", []) if isinstance(m, dict)}

        composer = metadata.get("Composer") or metadata.get("Creator") or metadata.get("Author")
        catalogue = metadata.get("Catalogue") or metadata.get("Opus") or metadata.get("Identifier")
        rights = metadata.get("Rights") or metadata.get("License") or ""
        public_domain = None
        if rights:
            low = str(rights).lower()
            if "public domain" in low or "cc0" in low or "creativecommons.org/publicdomain" in low:
                public_domain = True
            elif "copyright" in low or "all rights reserved" in low:
                public_domain = False

        manifest_id = str(item.get("id") or item.get("@id") or "")
        work_id = self._hash(manifest_id)

        return {
            "id": work_id,
            "title": title,
            "composer": composer,
            "catalogue": catalogue,
            "license": rights or None,
            "public_domain": public_domain,
            "key": metadata.get("Key") or metadata.get("Tonality"),
            "genre": metadata.get("Genre") or metadata.get("Form"),
            "resources": [
                {
                    "id": manifest_id,
                    "format": "iiif-manifest",
                    "mime_type": "application/ld+json",
                    "available": False,
                    "license": rights or None,
                    "download_url": manifest_id,
                    "view_url": manifest_id,
                    "thumbnail_url": item.get("thumbnail", [{}])[0].get("id") if item.get("thumbnail") else None,
                }
            ],
        }

    def _oai_to_work(self, metadata: dict[str, Any], identifier: str | None) -> dict[str, Any]:
        """Convert OAI-PMH record to work dict."""
        # Dublin Core fields

        def _first(md: dict[str, Any], key: str) -> str:
            val = md.get(key)
            if isinstance(val, list) and val:
                return str(val[0])
            return str(val or "")

        title = _first(metadata, "title")
        creator = _first(metadata, "creator")
        subject = _first(metadata, "subject")
        rights = _first(metadata, "rights")

        public_domain = None
        if rights:
            low = rights.lower()
            if "public domain" in low or "cc0" in low:
                public_domain = True
            elif "copyright" in low:
                public_domain = False

        work_id = self._hash(str(identifier or title))

        return {
            "id": work_id,
            "title": title,
            "composer": creator or None,
            "catalogue": subject or None,
            "license": rights or None,
            "public_domain": public_domain,
            "genre": subject or None,
            "resources": [
                {
                    "id": str(identifier or work_id),
                    "format": "iiif-manifest",
                    "mime_type": "application/ld+json",
                    "available": False,
                    "license": rights or None,
                    "download_url": f"{self._base_url}/manifests/{identifier}" if identifier else None,
                    "view_url": f"{self._base_url}/manifests/{identifier}" if identifier else None,
                    "thumbnail_url": None,
                }
            ],
        }

    def _manifest_to_work(self, manifest: dict[str, Any]) -> dict[str, Any]:
        """Convert IIIF Manifest to work dict."""
        label = manifest.get("label", {})
        title = self._first_label(label)

        metadata = {}
        for m in manifest.get("metadata", []):
            if isinstance(m, dict):
                lbl = m.get("label", {})
                val = m.get("value", {})
                label_str = self._first_label(lbl)
                value_str = self._first_label(val)
                if label_str and value_str:
                    metadata[label_str] = value_str

        composer = metadata.get("Composer") or metadata.get("Creator") or metadata.get("Author")
        catalogue = metadata.get("Catalogue") or metadata.get("Opus") or metadata.get("Identifier")
        rights = metadata.get("Rights") or metadata.get("License") or ""
        public_domain = None
        if rights:
            low = rights.lower()
            if "public domain" in low or "cc0" in low:
                public_domain = True
            elif "copyright" in low:
                public_domain = False

        manifest_id = str(manifest.get("id") or manifest.get("@id") or "")
        work_id = self._hash(manifest_id)

        # Extract canvas resources
        resources = []
        for seq in manifest.get("items", []):  # sequences
            for canvas in seq.get("items", []):  # canvases
                for ann in canvas.get("annotations", []):
                    for body in ann.get("body", []):
                        if isinstance(body, dict) and body.get("type") in ("Image", "Video", "Audio", "Text"):
                            thumb = canvas.get("thumbnail", [{}])[0].get("id") if canvas.get("thumbnail") else None
                            resources.append({
                                "id": body.get("id", ""),
                                "format": body.get("format", "iiif-resource"),
                                "mime_type": body.get("format"),
                                "available": True,
                                "license": rights or None,
                                "download_url": body.get("id"),
                                "view_url": canvas.get("id"),
                                "thumbnail_url": thumb,
                            })

        if not resources:
            resources = [{
                "id": manifest_id,
                "format": "iiif-manifest",
                "mime_type": "application/ld+json",
                "available": False,
                "license": rights or None,
                "download_url": manifest_id,
                "view_url": manifest_id,
                "thumbnail_url": manifest.get("thumbnail", [{}])[0].get("id") if manifest.get("thumbnail") else None,
            }]

        return {
            "id": work_id,
            "title": title,
            "composer": composer,
            "catalogue": catalogue,
            "license": rights or None,
            "public_domain": public_domain,
            "key": metadata.get("Key") or metadata.get("Tonality"),
            "genre": metadata.get("Genre") or metadata.get("Form"),
            "resources": resources,
        }

    def _first_label(self, label_obj: Any) -> str:
        """Extract first string from IIIF label object: { "en": ["Title"] } or "Title"."""
        if isinstance(label_obj, str):
            return label_obj
        if isinstance(label_obj, dict):
            for lang in ("en", "es", "fr", "de", "none", "und"):
                val = label_obj.get(lang)
                if isinstance(val, list) and val:
                    return str(val[0])
                if isinstance(val, str):
                    return val
            # fallback to first value
            for val in label_obj.values():
                if isinstance(val, list) and val:
                    return str(val[0])
                if isinstance(val, str):
                    return val
        return ""

    def _hash(self, text: str) -> str:
        import hashlib
        return hashlib.sha1(text.encode()).hexdigest()[:16]  # noqa: S324
