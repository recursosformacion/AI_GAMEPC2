"""Conector Wikidata: búsqueda SPARQL y extracción desde EntityData JSON.

No escribe en el catálogo: produce ``EnrichmentCandidate`` para el staging.
Datos de Wikidata = CC0. Cada valor apunta a la página del ítem como evidencia.
"""

from __future__ import annotations

import re
from typing import Any, cast

import requests

from src.osap.application.enrichment.models import EnrichmentCandidate

SPARQL_URL = "https://query.wikidata.org/sparql"
MEDIAWIKI_API = "https://www.wikidata.org/w/api.php"
ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
PAGE_URL = "https://www.wikidata.org/wiki/{qid}"
USER_AGENT = "OSAP-Enrichment/0.1 (+https://openmusicrepository.com)"
LICENSE = "CC0-1.0"
CONFIDENCE = 0.8

_TIME_RE = re.compile(r"[+-](\d{4})")

# Campos de persona que se emiten como candidatos (clave en el dict -> campo).
_PERSON_FIELDS = {
    "name": "name",
    "birth_year": "birth_year",
    "death_year": "death_year",
    "gnd": "gnd",
    "isni": "isni",
    "viaf": "viaf",
    "lccn": "lccn",
    "bnf": "bnf",
    "bne": "bne",
    "musicbrainz_artist": "musicbrainz_artist",
    "image": "image",
}
_PERSON_LISTS = {"nationality_qid": "nationality_qid", "occupation_qid": "occupation_qid"}

# Campos de obra.
_WORK_FIELDS = {
    "title": "title",
    "inception_year": "inception_year",
    "publication_year": "publication_year",
    "musicbrainz_work": "musicbrainz_work",
}
_WORK_LISTS = {
    "composer_qid": "composer_qid",
    "tonality_qid": "tonality_qid",
    "instrumentation_qid": "instrumentation_qid",
    "instance_of_qid": "instance_of_qid",
}


def looks_like_qid(value: str) -> bool:
    return bool(re.fullmatch(r"Q\d+", value.strip()))


def _entity(document: dict[str, Any], qid: str) -> dict[str, Any]:
    entities = document.get("entities")
    if isinstance(entities, dict):
        entity = entities.get(qid)
        if isinstance(entity, dict):
            return entity
    return {}


def _label(labels: Any, languages: tuple[str, ...]) -> str:
    if not isinstance(labels, dict):
        return ""
    for lang in languages:
        entry = labels.get(lang)
        if isinstance(entry, dict):
            value = entry.get("value")
            if isinstance(value, str) and value:
                return value
    return ""


def _claim_values(entity: dict[str, Any], prop: str) -> list[Any]:
    claims = entity.get("claims")
    if not isinstance(claims, dict):
        return []
    raw = claims.get(prop)
    if not isinstance(raw, list):
        return []
    values: list[Any] = []
    for statement in raw:
        if not isinstance(statement, dict):
            continue
        mainsnak = statement.get("mainsnak")
        if not isinstance(mainsnak, dict):
            continue
        datavalue = mainsnak.get("datavalue")
        if isinstance(datavalue, dict) and "value" in datavalue:
            values.append(datavalue["value"])
    return values


def _year(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("time")
    if not isinstance(raw, str):
        return None
    match = _TIME_RE.match(raw)
    return int(match.group(1)) if match else None


def _years(values: list[Any]) -> int | None:
    for value in values:
        year = _year(value)
        if year is not None:
            return year
    return None


def _strings(values: list[Any]) -> list[str]:
    return [v for v in values if isinstance(v, str) and v]


def _first(values: list[str]) -> str:
    return values[0] if values else ""


def _entity_ids(values: list[Any]) -> list[str]:
    ids: list[str] = []
    for value in values:
        if isinstance(value, dict):
            qid = value.get("id")
            if isinstance(qid, str) and qid:
                ids.append(qid)
    return ids


def extract_person(document: dict[str, Any], qid: str) -> dict[str, Any]:
    """Normaliza una persona de Wikidata a un dict plano (solo datos fiables)."""
    entity = _entity(document, qid)
    return {
        "qid": qid,
        "name": _label(entity.get("labels"), ("es", "en")),
        "birth_year": _years(_claim_values(entity, "P569")),
        "death_year": _years(_claim_values(entity, "P570")),
        "gnd": _first(_strings(_claim_values(entity, "P227"))),
        "isni": _first(_strings(_claim_values(entity, "P213"))),
        "viaf": _first(_strings(_claim_values(entity, "P214"))),
        "lccn": _first(_strings(_claim_values(entity, "P244"))),
        "bnf": _first(_strings(_claim_values(entity, "P268"))),
        "bne": _first(_strings(_claim_values(entity, "P950"))),
        "musicbrainz_artist": _first(_strings(_claim_values(entity, "P434"))),
        "nationality_qid": _entity_ids(_claim_values(entity, "P27")),
        "occupation_qid": _entity_ids(_claim_values(entity, "P106")),
        "image": _first(_strings(_claim_values(entity, "P18"))),
    }


def extract_work(document: dict[str, Any], qid: str) -> dict[str, Any]:
    """Normaliza una obra musical de Wikidata a un dict plano."""
    entity = _entity(document, qid)
    return {
        "qid": qid,
        "title": _label(entity.get("labels"), ("es", "en")),
        "composer_qid": _entity_ids(_claim_values(entity, "P86")),
        "inception_year": _years(_claim_values(entity, "P571")),
        "publication_year": _years(_claim_values(entity, "P577")),
        "tonality_qid": _entity_ids(_claim_values(entity, "P826")),
        "instrumentation_qid": _entity_ids(_claim_values(entity, "P870")),
        "musicbrainz_work": _first(_strings(_claim_values(entity, "P435"))),
        "instance_of_qid": _entity_ids(_claim_values(entity, "P31")),
    }


def _candidate(entity_type: str, key: str, field: str, value: str, qid: str) -> EnrichmentCandidate:
    return EnrichmentCandidate(
        entity_type=entity_type,
        entity_key=key,
        field=field,
        value=value,
        source="wikidata",
        evidence_url=PAGE_URL.format(qid=qid),
        confidence=CONFIDENCE,
        license=LICENSE,
    )


def person_candidates(
    qid: str, data: dict[str, Any], entity_key: str | None = None
) -> list[EnrichmentCandidate]:
    key = entity_key or qid
    out: list[EnrichmentCandidate] = []
    for field_name, field in _PERSON_FIELDS.items():
        value = data.get(field_name)
        if value is None or value == "":
            continue
        out.append(_candidate("person", key, field, str(value), qid))
    for field_name, field in _PERSON_LISTS.items():
        for item in data.get(field_name) or []:
            out.append(_candidate("person", key, field, str(item), qid))
    return out


def work_candidates(
    qid: str, data: dict[str, Any], entity_key: str | None = None
) -> list[EnrichmentCandidate]:
    key = entity_key or qid
    out: list[EnrichmentCandidate] = []
    for field_name, field in _WORK_FIELDS.items():
        value = data.get(field_name)
        if value is None or value == "":
            continue
        out.append(_candidate("work", key, field, str(value), qid))
    for field_name, field in _WORK_LISTS.items():
        for item in data.get(field_name) or []:
            out.append(_candidate("work", key, field, str(item), qid))
    return out


def _binding_value(binding: dict[str, Any], key: str) -> str:
    entry = binding.get(key)
    if isinstance(entry, dict):
        value = entry.get("value")
        if isinstance(value, str):
            return value
    return ""


def _year_from_datetime(text: str) -> int | None:
    match = re.match(r"^(-?\d{1,4})-", text or "")
    return int(match.group(1)) if match else None


def _parse_person_batch(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = data.get("results")
    bindings = results.get("bindings") if isinstance(results, dict) else None
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(bindings, list):
        return out
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        uri = _binding_value(binding, "item")
        qid = uri.rsplit("/", 1)[-1] if "/" in uri else uri
        if not qid.startswith("Q"):
            continue
        record = out.setdefault(
            qid,
            {
                "qid": qid,
                "name": "",
                "birth_year": None,
                "death_year": None,
                "gnd": "",
                "isni": "",
                "viaf": "",
                "lccn": "",
                "bnf": "",
                "bne": "",
                "musicbrainz_artist": "",
                "image": "",
                "nationality_qid": [],
                "occupation_qid": [],
            },
        )
        if not record["name"]:
            record["name"] = _binding_value(binding, "itemLabel")
        if record["birth_year"] is None:
            record["birth_year"] = _year_from_datetime(_binding_value(binding, "dob"))
        if record["death_year"] is None:
            record["death_year"] = _year_from_datetime(_binding_value(binding, "dod"))
        for var, target in (
            ("gnd", "gnd"),
            ("isni", "isni"),
            ("viaf", "viaf"),
            ("lccn", "lccn"),
            ("bnf", "bnf"),
            ("bne", "bne"),
            ("mb", "musicbrainz_artist"),
            ("image", "image"),
        ):
            if not record[target]:
                record[target] = _binding_value(binding, var)
    return out


class WikidataSource:
    """Cliente mínimo de Wikidata (inyectable para pruebas)."""

    def __init__(self, session: Any | None = None, timeout: int = 30) -> None:
        self._session = session if session is not None else requests.Session()
        self._timeout = timeout

    def _get(self, url: str, params: dict[str, str] | None, accept: str) -> dict[str, Any]:
        headers = {"User-Agent": USER_AGENT, "Accept": accept}
        response = self._session.get(
            url, params=params, headers=headers, timeout=self._timeout
        )
        response.raise_for_status()
        payload = response.json()
        return cast("dict[str, Any]", payload) if isinstance(payload, dict) else {}

    def search(self, text: str, kind: str) -> list[dict[str, str]]:
        """Resuelve nombre/título a QIDs (MediaWiki wbsearchentities; rápido)."""
        if kind not in {"person", "work"}:
            raise ValueError(f"kind inválido: {kind}")
        params = {
            "action": "wbsearchentities",
            "search": text.strip(),
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": "15",
            "format": "json",
        }
        data = self._get(MEDIAWIKI_API, params, "application/json")
        return _parse_entities(data)

    def entity(self, qid: str) -> dict[str, Any]:
        return self._get(ENTITY_URL.format(qid=qid), None, "application/json")

    def fetch_persons_batch(self, qids: list[str]) -> dict[str, dict[str, Any]]:
        """Enriquece varias personas (QIDs) en una sola consulta SPARQL ``VALUES``."""
        cleaned = [q for q in qids if looks_like_qid(q)]
        if not cleaned:
            return {}
        values = " ".join(f"wd:{q}" for q in cleaned)
        query = (
            "SELECT ?item ?itemLabel ?dob ?dod ?gnd ?isni ?viaf ?lccn ?bnf ?bne ?mb ?image WHERE { "
            f"VALUES ?item {{ {values} }} "
            "OPTIONAL { ?item wdt:P569 ?dob } "
            "OPTIONAL { ?item wdt:P570 ?dod } "
            "OPTIONAL { ?item wdt:P227 ?gnd } "
            "OPTIONAL { ?item wdt:P213 ?isni } "
            "OPTIONAL { ?item wdt:P214 ?viaf } "
            "OPTIONAL { ?item wdt:P244 ?lccn } "
            "OPTIONAL { ?item wdt:P268 ?bnf } "
            "OPTIONAL { ?item wdt:P950 ?bne } "
            "OPTIONAL { ?item wdt:P434 ?mb } "
            "OPTIONAL { ?item wdt:P18 ?image } "
            'SERVICE wikibase:label { bd:serviceParam wikibase:language "es,en". } '
            "}"
        )
        data = self._get(
            SPARQL_URL, {"query": query, "format": "json"}, "application/sparql-results+json"
        )
        return _parse_person_batch(data)


def _parse_entities(data: dict[str, Any]) -> list[dict[str, str]]:
    items = data.get("search")
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        qid = item.get("id")
        if not isinstance(qid, str) or not qid:
            continue
        label = item.get("label")
        description = item.get("description")
        out.append(
            {
                "qid": qid,
                "label": label if isinstance(label, str) else "",
                "description": description if isinstance(description, str) else "",
            }
        )
    return out
