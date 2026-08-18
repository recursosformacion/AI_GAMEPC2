"""Enriquecimiento abierto de identificadores, de donde se pueda.

  * Compositor → ISNI, VIAF, LCCN, MusicBrainz, Wikidata (Wikidata SPARQL).
  * Obra → ISWC best-effort (MusicBrainz work `inc=iswcs`), wikidata_work (Wikidata).

ISWC/IPI de la autoridad (CISAC) quedan pendientes de credenciales (`cisac_client`).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

import requests

from src.osap.application.metadata_normalizer import MetadataNormalizer
from src.osap.infrastructure.identifiers.archive import ComposerRecord

_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_SPARQL = "https://query.wikidata.org/sparql"
_MUSICBRAINZ = "https://musicbrainz.org/ws/2"
_USER_AGENT = "osap-identifiers/0.1 (reconstruction; read-only)"
_COMPOSER_OCCUPATION = "Q36834"  # compositor


def composer_identifiers(name: str, timeout: int = 30) -> ComposerRecord | None:
    """ISNI/VIAF/LCCN/MusicBrainz de un compositor vía Wikidata (búsqueda + SPARQL).

    Alias-aware: entre los candidatos de Wikidata elige el que canonicamente coincide con
    el nombre (p. ej. "J. Scott Skinner" → "James Scott Skinner"), no solo el primero.
    `timeout` en segundos por llamada (agresivo para no bloquear la pasada).
    """
    name = (name or "").strip()
    if not name:
        return None
    target = MetadataNormalizer.comparison_composer(name)
    qid = _search_entity(name, target, timeout)
    if not qid and len(name.split()) > 1:
        # Fallback por apellido: "J. Scott Skinner" → buscar "Skinner" y matchear canónico.
        qid = _search_entity(name.split()[-1], target, timeout)
    if not qid:
        return None
    ids, aliases = _composer_ids(qid, timeout)
    if not ids:
        return None
    return ComposerRecord(
        composer_key=_key(name),
        canonical_name=ids.get("label") or name,
        aliases=aliases,
        isni=ids.get("isni"),
        wikidata=qid,
        viaf=ids.get("viaf"),
        musicbrainz=ids.get("mbid"),
        lccn=ids.get("lccn"),
        source="wikidata",
    )


def work_iswc(title: str) -> str | None:
    """ISWC de una obra desde MusicBrainz (best-effort: solo si el work la tiene)."""
    title = (title or "").strip()
    if not title:
        return None
    mbid = _musicbrainz_work_mbid(title)
    if not mbid:
        return None
    return _musicbrainz_work_iswc(mbid)


def work_wikidata(title: str) -> str | None:
    """Q-id de una obra musical en Wikidata (para `wikidata_work`)."""
    title = (title or "").strip()
    if not title:
        return None
    qid = _search_entity(title)
    return qid


# --- Wikidata ---


def _search_entity(text: str, target_key: str = "", timeout: int = 30) -> str | None:
    params = {
        "action": "wbsearchentities",
        "search": text,
        "language": "en",
        "type": "item",
        "format": "json",
        "limit": "20",
    }
    try:
        resp = requests.get(_WIKIDATA_API, params=params, headers={"User-Agent": _USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
        results = resp.json().get("search", [])
    except Exception:  # noqa: BLE001
        return None

    if not target_key:
        for item in results:
            qid = item.get("id")
            if isinstance(qid, str) and qid.startswith("Q"):
                return qid
        return None

    # Preferir el candidato cuyo label canónicamente coincide con el nombre buscado
    # (p. ej. "J. S. Bach" -> "Johann Sebastian Bach").
    for item in results:
        qid = item.get("id")
        label = item.get("label")
        if not isinstance(qid, str) or not qid.startswith("Q") or not label:
            continue
        if MetadataNormalizer.comparison_composer(str(label)) == target_key:
            return qid
    for item in results:
        qid = item.get("id")
        if isinstance(qid, str) and qid.startswith("Q"):
            return qid
    return None


def _composer_ids(qid: str, timeout: int = 30) -> tuple[dict[str, str], list[str]]:
    query = f"""
SELECT ?itemLabel ?viaf ?isni ?lccn ?mbid ?alias WHERE {{
  wd:{qid} wdt:P31 wd:Q5 .
  OPTIONAL {{ wd:{qid} wdt:P214 ?viaf }}
  OPTIONAL {{ wd:{qid} wdt:P213 ?isni }}
  OPTIONAL {{ wd:{qid} wdt:P244 ?lccn }}
  OPTIONAL {{ wd:{qid} wdt:P434 ?mbid }}
  OPTIONAL {{ wd:{qid} skos:altLabel ?alias }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language 'en'. }}
}}
LIMIT 40
"""
    try:
        resp = requests.get(
            _SPARQL,
            params={"query": query, "format": "json"},
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        bindings = resp.json().get("results", {}).get("bindings", [])
    except Exception:  # noqa: BLE001
        return {}, []
    if not bindings:
        return {}, []
    ids: dict[str, str] = {}
    aliases: list[str] = []
    for b in bindings:
        ids.setdefault("label", _val(b, "itemLabel"))
        for key, prop in (("viaf", "viaf"), ("isni", "isni"), ("lccn", "lccn"), ("mbid", "mbid")):
            if not ids.get(key) and _val(b, prop):
                ids[key] = _val(b, prop)
        if _val(b, "alias"):
            aliases.append(_val(b, "alias"))
    aliases = list(dict.fromkeys(a for a in aliases if a != ids.get("label")))
    return ids, aliases


def _val(binding: dict[str, object], key: str) -> str:
    value = binding.get(key)
    return value.get("value", "") if isinstance(value, dict) else ""


# --- MusicBrainz ---


def _musicbrainz_work_mbid(title: str) -> str | None:
    query = urllib.parse.quote(f'work:"{title.replace(chr(34), "")}"')
    url = f"{_MUSICBRAINZ}/work/?query={query}&fmt=json&limit=3"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"}), timeout=25
        ) as response:
            doc = json.loads(response.read())
    except Exception:  # noqa: BLE001
        return None
    works = doc.get("works") if isinstance(doc, dict) else []
    if isinstance(works, list) and works and isinstance(works[0], dict):
        return works[0].get("id")
    return None


def _musicbrainz_work_iswc(mbid: str) -> str | None:
    url = f"{_MUSICBRAINZ}/work/{mbid}?inc=iswcs&fmt=json"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"}), timeout=25
        ) as response:
            doc = json.loads(response.read())
    except Exception:  # noqa: BLE001
        return None
    iswc = doc.get("iswc") if isinstance(doc, dict) else None
    return str(iswc) if iswc else None


def _key(name: str) -> str:
    from src.osap.application.metadata_normalizer import MetadataNormalizer

    return MetadataNormalizer.comparison_composer(name) or name.strip().lower()
