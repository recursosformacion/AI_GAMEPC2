"""Atribución obra → compositor vía Wikidata (works musicales).

Cuando una obra está identificada pero ningún proveedor aporta el compositor, se consulta
Wikidata por **obras musicales** (P31=Q2188189) que coincidan con el título y se recupera
su compositor (P86). Es una atribución basada en la OBRA, no en asumir anónimo: si no hay
obra ni compositor, devuelve vacío (desconocido).

Se usa la API ligera `wbsearchentities` para hallar el item y una SPARQL corta para su
compositor. No está en el matcher determinista: es un paso de enriquecimiento externo.
"""

from __future__ import annotations

from typing import Any

import requests

_SEARCH_URL = "https://www.wikidata.org/w/api.php"
_SPARQL_URL = "https://query.wikidata.org/sparql"
_USER_AGENT = "osap-work-attributor/0.1 (reconstruction; read-only)"

_COMPOSER_PROP = "P86"  # composer
_MUSICAL_WORK = "Q2188189"  # musical work


class WikidataWorkAttributor:
    provider_id = "wikidata_work"

    def attribute(self, work_title: str, catalog: str | None = None) -> list[dict[str, object]]:
        title = (work_title or "").strip()
        if not title:
            return []
        item_ids = self._search_items(title)
        if not item_ids:
            return []
        out: list[dict[str, object]] = []
        for qid in item_ids[:5]:
            composer = self._composer_of(qid)
            if composer:
                composer["qid"] = qid
                out.append(composer)
        return out

    def _search_items(self, title: str) -> list[str]:
        params = {
            "action": "wbsearchentities",
            "search": title,
            "language": "en",
            "type": "item",
            "format": "json",
            "limit": "10",
        }
        try:
            resp = requests.get(_SEARCH_URL, params=params, headers={"User-Agent": _USER_AGENT}, timeout=30)
            resp.raise_for_status()
            results = resp.json().get("search", [])
        except Exception:  # noqa: BLE001
            return []
        ids: list[str] = []
        for item in results:
            qid = item.get("id")
            if qid and qid.startswith("Q"):
                ids.append(qid)
        return ids

    def _composer_of(self, work_qid: str) -> dict[str, object] | None:
        query = f"""
SELECT ?composer ?composerLabel ?cl ?viaf ?mbid WHERE {{
  wd:{work_qid} wdt:{_COMPOSER_PROP} ?composer .
  OPTIONAL {{ ?composer rdfs:label ?cl . FILTER(LANG(?cl) = 'en') }}
  OPTIONAL {{ ?composer wdt:P214 ?viaf }}
  OPTIONAL {{ ?composer wdt:P434 ?mbid }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language 'en'. }}
}}
LIMIT 5
"""
        try:
            resp = requests.get(
                _SPARQL_URL,
                params={"query": query, "format": "json"},
                headers={"User-Agent": _USER_AGENT},
                timeout=40,
            )
            resp.raise_for_status()
            bindings = resp.json().get("results", {}).get("bindings", [])
        except Exception:  # noqa: BLE001
            return None
        if not bindings:
            return None
        first = bindings[0]
        composer_qid = _qid(_val(first, "composer"))
        composer = _val(first, "composerLabel") or _val(first, "cl") or self._label_of(composer_qid) or composer_qid
        external_ids: dict[str, str] = {}
        if _val(first, "viaf"):
            external_ids["viaf"] = _val(first, "viaf")
        if _val(first, "mbid"):
            external_ids["musicbrainz"] = _val(first, "mbid")
        return {
            "name": composer,
            "composer_qid": composer_qid,
            "confidence": 0.6,
            "external_ids": external_ids,
        }

    def _label_of(self, qid: str) -> str:
        """Label fiable del item vía wbgetentities (fallback cuando SPARQL label falla)."""
        if not qid.startswith("Q"):
            return ""
        params = {"action": "wbgetentities", "ids": qid, "props": "labels", "languages": "en", "format": "json"}
        try:
            resp = requests.get(_SEARCH_URL, params=params, headers={"User-Agent": _USER_AGENT}, timeout=30)
            resp.raise_for_status()
            entity = resp.json().get("entities", {}).get(qid, {})
            labels = entity.get("labels", {})
            value = labels.get("en", {}).get("value") if isinstance(labels, dict) else None
            return str(value) if value else ""
        except Exception:  # noqa: BLE001
            return ""


def _val(binding: Any, key: str) -> str:
    value = binding.get(key, {})
    if isinstance(value, dict):
        raw = value.get("value", "")
        return str(raw) if raw is not None else ""
    return ""


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1] if uri.startswith("http") else uri
