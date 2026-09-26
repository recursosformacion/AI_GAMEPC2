#!/usr/bin/env python
"""Indexador local de obras — multi-proveedor (paso 1 del índice).

Lee obras de varios proveedores y puebla el índice local
(`index_works` + `index_representations` en la BD de osap-api), normalizando títulos
(`title_key`) y compositores (canonical + `person_id` del Maestro) y deduplicando por
(`title_key`, `person_id`). La normalización es determinista: el índice GUARDA el
resultado, no lo recalcula por búsqueda.

Proveedores (selección con `--providers`):
  omr          -> corpus OMR
                                        (osap-storage.works)
                                               [musicxml]
  cpdl         -> corpus CPDL            (osap-storage.works, works_origin='CPDL')
                                               [pdf/musicxml]
  imslp        -> Worklist API de IMSLP (paginada por start)               [pdf/página]
  mutopia      -> make-table.cgi (listing completo, paginado por startat)  [pdf+midi]
  musicbrainz  -> dump local mbdump (work + l_artist_work + artist)        [metadata]

CPDL SÍ se indexa aquí: su corpus ya está materializado en `osap-storage.works`
(`works_origin='CPDL'`, con personas y recursos propios), igual que OMR. Así la búsqueda
por canción y la ficha de compositor devuelven el mismo conjunto y `works_count` cuadra.
El voicing son las formaciones de `ensembles` vía `work_ensembles` (fuente única: storage).

OMR construye `download_url` como `{storage}/api/download/{file_id}` (el endpoint de
osap-storage redirige 302 al CDN/R2) y marca `available=1`. MusicBrainz por defecto solo
indexa tipos de música artística (`--mb-types art`); usa `--mb-types all` para todo.

Uso (en osap-api, con PYTHONPATH=osap-api):
    python script/index_works.py --providers omr,imslp --limit 1000
    python script/index_works.py --providers mutopia
    python script/index_works.py --providers omr --omr-base-url https://storage.openmusicrepository.com
    python script/index_works.py --providers musicbrainz --mb-dump <mbdump_dir> --mb-types art
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

import pymysql

from src.osap.application.metadata_normalizer import MetadataNormalizer, title_key
from src.osap.infrastructure.providers.fetchers.mutopia_fetcher import _parse_table

_NORMALIZER = MetadataNormalizer()

_ANON = {
    "anon", "anon.", "anonymous", "anonymus", "anonimo", "anónimo", "trad", "trad.",
    "traditional", "traditionnel", "tradicional", "traditionell", "unattributed",
    "unknown", "author unknown", "urheber unbekannt", "urheber unbek.",
    "na", "n/a", "n.a.", "none", "unknown composer", "composer",
}

_IMSLP_API = "https://imslp.org/imslpscripts/API.ISCR.php"
_MUTOPIA_CGI = "https://www.mutopiaproject.org/cgibin/make-table.cgi"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# MusicBrainz work types de "música artística" (las demás son pop/soundtrack/literaria).
_MB_ART_TYPES = {
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
    "13", "14", "15", "16", "18", "19", "20", "24",
}
_MB_COMPOSER_LINK_TYPE = "168"


def composer_key(raw: str) -> str:
    """Clave de identidad por nombre normalizado (coherente con identity_resolver)."""
    text = (raw or "").strip()
    if not text:
        return ""
    low = text.lower().replace("'", "").replace("\u2019", "")
    if low in _ANON or low.startswith("urheber unbekannt"):
        return "anonymous"
    text = re.sub(r"\s+\d{3,4}\s*$", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    tokens = re.findall(r"[a-z\u00e0-\u00ff]+", low)
    if not tokens:
        return ""
    if len(tokens) > 1 and tokens[-2] == "o":
        surname = "o" + tokens[-1]
        given = tokens[:-2]
    else:
        surname = tokens[-1]
        given = tokens[:-1]
    firsts = "".join(t[0] for t in given)
    return f"{firsts} {surname}".strip()


def _reverse_last_first(name: str) -> str:
    """'Ferrari, Carlotta' -> 'Carlotta Ferrari' (formato de IMSLP)."""
    if "," in name:
        last, first = name.rsplit(",", 1)
        last = last.strip()
        first = first.strip()
        if last and first:
            return f"{first} {last}"
    return name.strip()


_GENERIC_TITLE_WORDS = {
    "major", "minor", "concerto", "suite", "sonata", "sinfonia", "symphony", "prelude",
    "aria", "partita", "trio", "quartet", "quintet", "sextet", "etude", "etudes",
    "nocturne", "variations", "variation", "mass", "missa", "requiem", "canon",
    "fugue", "fantasia", "opus", "volume", "complete", "arrangement", "version",
    "transcription", "vocal", "score", "piano", "violin", "viola", "cello", "flute",
    "oboe", "trumpet", "recorder", "strings", "orchestra", "chamber", "organ",
    "harpsichord", "gamba", "basso", "continuo", "con", "for", "and", "with", "from",
}

# Prefijos de catálogo donde UN número identifica la obra de forma única (K.618, BWV.232,
# D.795…). En series (Op., TWV, Hob. con subnúmero) se exige además el subnúmero.
_UNIQUE_CATALOGUE_PREFIXES = ("k", "kv", "bwv", "d", "wq", "s", "l", "hob")


_CAT_PREFIX_SYNONYMS = {
    "kv": "k", "kochel": "k", "koch": "k",
    "opus": "op", "op.": "op",
    "bwv.": "bwv", "hob.": "hob", "wq.": "wq",
    "s.": "s", "l.": "l", "d.": "d",
}


def _canonical_catalogue_identity(catalogue: str | None) -> str:
    """Catálogo completo normalizado con prefijos unificados (KV 618 == K 618 -> "k 618").

    No usa `title_key` (pensado para títulos: descarta números de catálogo); conserva
    prefijo y números, y separa el compacto ``k618`` en ``k 618``.
    """
    text = unicodedata.normalize("NFKD", str(catalogue or "")).encode("ascii", "ignore").decode().lower()
    tokens = re.sub(r"[^a-z0-9]+", " ", text).split()
    if not tokens:
        return ""
    if len(tokens) == 1:
        m = re.match(r"^([a-z]+)(\d.*)$", tokens[0])
        if m:
            tokens = [m.group(1), m.group(2)]
    tokens[0] = _CAT_PREFIX_SYNONYMS.get(tokens[0], tokens[0])
    return " ".join(tokens)[:128]


def _significant_tokens(title: str, composer: str | None = None) -> set[str]:
    """Palabras del título con valor identificativo (>=3 letras, sin genéricos NI
    tokens del compositor).

    En PDMX el compositor viene DENTRO del título ("Frédéric Chopin: Prelude…"); si no
    se excluye, cualquier obra del mismo autor reduce a {ric, chopin} y todas colapsan
    en una sola obra (bug de agrupación de OMR).
    """
    composer_tokens = set(title_key(composer).split()) if composer else set()
    return {
        t
        for t in title_key(title).split()
        if len(t) >= 3 and not t.isdigit() and t not in _GENERIC_TITLE_WORDS
        and t not in composer_tokens
    }


def _is_unique_catalogue(catalogue_norm: str) -> bool:
    """True si el catálogo normalizado identifica una única obra (no una serie).

    Ejemplos: ``k618``, ``bwv232``, ``d795`` -> True; ``twv 55``, ``op 1`` -> False
    (necesitan subnúmero: ``twv 55 d6``, ``op 1 no 8``).
    """
    text = catalogue_norm.strip()
    if not text:
        return False
    parts = text.split()
    numbers = [p for p in parts if p.isdigit()]
    prefix = parts[0]
    if prefix in _UNIQUE_CATALOGUE_PREFIXES and len(numbers) == 1:
        return True
    # Con subnúmero (dos números) cualquier prefijo sirve: "op 1 no 8", "twv 55 d6".
    return len(numbers) >= 2


def _shares_significant_token(a: str, b: str, composer: str | None = None) -> bool:
    return bool(_significant_tokens(a, composer) & _significant_tokens(b, composer))


def _tokens_subset_sets(a: set[str], b: set[str]) -> bool:
    """Versión sobre conjuntos ya normalizados (evita recalcular `title_key`)."""
    if not a or not b:
        return False
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    return len(small) >= 2 and small <= big


def _tokens_subset(a: str, b: str, composer: str | None = None) -> bool:
    """True si las palabras significativas de `a` están contenidas en las de `b` (o al revés).

    Permite anclar títulos sin catálogo ("Ave Verum", "Ave Verum Corpus - TTBB") a la obra
    ya identificada ("Mozart: Ave Verum Corpus K. 618") sin unir obras distintas: exige al
    menos 2 palabras significativas PROPIAS del título (excluido el compositor).
    """
    ta, tb = _significant_tokens(a, composer), _significant_tokens(b, composer)
    if not ta or not tb:
        return False
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return len(small) >= 2 and small <= big


def _shares_title_token(a: str, b: str) -> bool:
    """True si dos títulos comparten alguna palabra significativa (>=4 letras)."""
    ta = {t for t in title_key(a).split() if len(t) >= 4}
    tb = {t for t in title_key(b).split() if len(t) >= 4}
    return bool(ta & tb)


def _catalogue_key(catalogue: str | None) -> str | None:
    if not catalogue:
        return None
    return re.sub(r"[^a-z0-9]", "", catalogue.lower()) or None


# Prefijos de catálogo para extraer el catálogo del compositor del título
# (KV/K./BWV/Op./D./Hob./R./Wq./S./L./TwV y sinónimos de Köchel).
_CATALOGUE_PREFIX_RE = re.compile(
    r"(?i)(?<![a-z0-9])"
    r"((?:bwv|kv|kochel(?:[^a-z0-9]+ver(?:zeichnis)?)?|k\u00f6chel|koch(?:\.?\s*ver)?|k\.?|op\.?|opus|hob\.?|d\.?|r\.?|wq\.?|s\.?|l\.?|twv)\s*\.?\s*(?:no\.?\s*)?)"
    r"(\d{1,4}[a-z]?(?:[-/.]\d{1,3}[a-z]?)*|[IVXLCDM]{1,6}\s*:\s*\d{1,3})"
)


def _extract_composer_catalogue(title: str) -> str | None:
    """Detecta el catálogo del compositor en el título (KV 618, BWV 232, Op. 27...)."""
    m = _CATALOGUE_PREFIX_RE.search(title or "")
    if not m:
        return None
    prefix = unicodedata.normalize("NFKD", m.group(1)).encode("ascii", "ignore").decode().strip()
    prefix = re.sub(r"\s+", " ", prefix).rstrip(" .")
    number = m.group(2)
    if prefix.lower() in ("k", "kv", "koch", "kochel"):
        prefix = "K"
    return f"{prefix} {number}"


def _is_anon(name: str | None) -> bool:
    low = re.sub(r"[?¿¡!.]+\s*$", "", (name or "").strip().lower())
    return low in _ANON or low.startswith("urheber unbekannt")


def _resolve_person(
    conn: pymysql.Connection,
    raw_name: str | None,
    cache: dict[str, tuple[str | None, str | None]],
) -> tuple[str | None, str | None]:
    """Resuelve un nombre a (persons_id, persons_name) del Maestro.

    El índice **no normaliza**: si resuelve, copia el nombre canónico de `persons`; si no
    resuelve, devuelve (None, None) y se conserva el texto del proveedor tal cual (nunca
    `canonical_composer`, que producía inventos como "afwa mozart").
    """
    if not raw_name or _is_anon(raw_name):
        return None, None
    key = composer_key(raw_name)
    if key in cache:
        return cache[key]
    cid: str | None = None
    cname: str | None = None
    try:
        with conn.cursor() as cur:
            # Dos consultas (nombre → alias) para que MySQL use los índices: el `OR` con
            # JOIN forzaba un escaneo de `persons`/`persons_aliases` por cada nombre.
            cur.execute(
                "SELECT persons_id AS id, persons_name AS name FROM persons "
                "WHERE persons_status = 'active' AND persons_name = %s LIMIT 1",
                (raw_name,),
            )
            row = cur.fetchone()
            if row:
                cid, cname = row["id"], row["name"]
            if cid is None:
                cur.execute(
                    "SELECT p.persons_id AS id, p.persons_name AS name FROM persons_aliases a "
                    "JOIN persons p ON p.persons_id = a.person_id "
                    "WHERE a.person_aliases_normalized_alias = %s "
                    "AND p.persons_status = 'active' LIMIT 1",
                    (key,),
                )
                row = cur.fetchone()
                if row:
                    cid, cname = row["id"], row["name"]
    except pymysql.err.ProgrammingError:
        cid = cname = None
    if cid and cid in _PERSON_ID_CANON:
        cid, cname = _PERSON_ID_CANON[cid]
    if cid is None:
        canon = _PERSON_BEST.get(_person_name_key(raw_name))
        if canon:
            cid, cname = canon
    cache[key] = (cid, cname)
    return cid, cname


_PERSON_BEST: dict[frozenset, tuple[str | None, str | None]] = {}
_PERSON_ID_CANON: dict[str, tuple[str | None, str | None]] = {}


def _person_name_key(name: str | None) -> frozenset:
    cleaned = _NORMALIZER.comparison_composer(str(name or "").replace(",", " "))
    return frozenset(t for t in cleaned.split() if t)


def _load_person_canon(conn: pymysql.Connection) -> None:
    """Mapa persona→canónico (clase dominante por obras de rol 1, orden-insensible).

    Hace **converger** el build con la consolidación: todo compositor se resuelve a la
    MISMA persona dominante, así reindexar no crea filas nuevas ni nombres variantes.
    """
    _PERSON_BEST.clear()
    _PERSON_ID_CANON.clear()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT persons_id, persons_name FROM persons WHERE persons_status='active'"
            )
            persons = cur.fetchall()
            cur.execute(
                "SELECT works_person_roles_person_id AS pid, COUNT(*) AS n "
                "FROM works_person_roles WHERE works_person_roles_role_id = 1 GROUP BY pid"
            )
            counts = {str(r["pid"]): int(r["n"]) for r in cur.fetchall()}
            cur.execute(
                "SELECT person_id, person_aliases_normalized_alias AS a FROM persons_aliases"
            )
            aliases = cur.fetchall()
    except pymysql.err.ProgrammingError:
        return
    by_id = {str(p["persons_id"]): str(p["persons_name"]) for p in persons}
    keys = {pid: _person_name_key(name) for pid, name in by_id.items()}
    dominant: dict[frozenset, str] = {}
    for pid, key in keys.items():
        if not key:
            continue
        cur_best = dominant.get(key)
        if cur_best is None or counts.get(pid, 0) > counts.get(cur_best, 0):
            dominant[key] = pid
    for pid, key in keys.items():
        dom = dominant.get(key, pid)
        canon = (dom, by_id.get(dom, by_id[pid]))
        _PERSON_ID_CANON[pid] = canon
        if key:
            _PERSON_BEST[key] = canon
    for a in aliases:
        canon = _PERSON_ID_CANON.get(str(a["person_id"]))
        if canon:
            _PERSON_BEST.setdefault(_person_name_key(a["a"]), canon)


# ---------------------------------------------------------------- providers


# Etiquetas para obras cuyo tipo de atribución está marcado en `works` (no hay persona).
_ATTR_LABELS = {
    "ANONIMA": "Anónimo",
    "TRADICIONAL": "Tradicional",
    "POPULAR": "Popular",
    "DESCONOCIDO": "Desconocido",
}


def _iter_omr(
    omr: pymysql.Connection, from_id: int, limit: int, storage_base: str, batch: int = 2000
):
    """Obras del corpus OMR/PDMX (`works` de osap-storage con `works_origin='PDMX'`).

    CPDL tiene su propio proveedor (`_iter_cpdl`): NO se indexa aquí para no duplicar
    la obra bajo dos proveedores. Construye `download_url` como
    ``{storage_base}/api/download/{file_id}`` (el endpoint de storage redirige 302 al
    CDN/R2) y marca `available=1` cuando hay fichero. Pagina por PK.
    """
    base = storage_base.rstrip("/")
    last_id = from_id
    emitted = 0
    while limit <= 0 or emitted < limit:
        take = batch if limit <= 0 else min(batch, limit - emitted)
        with omr.cursor() as cur:
            cur.execute(
                "SELECT id, works_title AS title, works_catalogue AS catalogue, "
                "works_year AS year, works_instrumentation AS instrumentation, "
                "works_attr_type AS attr_type "
                "FROM works WHERE works_origin='PDMX' AND id > %s ORDER BY id LIMIT %s",
                (last_id, take),
            )
            works = cur.fetchall()
        if not works:
            return
        ids = [w["id"] for w in works]
        placeholders = ",".join(["%s"] * len(ids))
        composers: dict[int, tuple[str, str]] = {}
        files: dict[int, tuple[int, int, int]] = {}
        genres: dict[int, tuple[str, int]] = {}
        with omr.cursor() as cur:
            # Composer/atribución: rol 1 (compositor) en `works_person_roles` + `persons`.
            cur.execute(
                "SELECT r.works_person_roles_work_id AS work_id, p.persons_name AS composer, "
                "r.works_person_roles_person_id AS person_id "
                "FROM works_person_roles r "
                "JOIN persons p ON p.persons_id = r.works_person_roles_person_id "
                f"WHERE r.works_person_roles_work_id IN ({placeholders}) "
                "AND r.works_person_roles_role_id = 1 "
                "ORDER BY r.works_person_roles_work_id, r.works_person_roles_order, "
                "r.works_person_roles_id",
                ids,
            )
            for row in cur.fetchall():
                composers.setdefault(
                    int(row["work_id"]),
                    (str(row["composer"] or ""), str(row["person_id"] or "")),
                )
            # Fichero: `works_resources`, prefiriendo partitura (MXL/MusicXML).
            cur.execute(
                "SELECT wr.id AS res_id, wr.works_resources_work_id AS work_id, "
                "wr.works_resources_file_id AS file_id, wr.works_resources_type AS rtype "
                "FROM works_resources wr "
                f"WHERE wr.works_resources_work_id IN ({placeholders}) "
                "AND wr.works_resources_file_id IS NOT NULL",
                ids,
            )
            for row in cur.fetchall():
                rtype = str(row["rtype"] or "")
                rank = 0 if rtype == "MXL" else (1 if rtype == "MusicXML" else 99)
                if rank == 99:
                    continue
                work_id = int(row["work_id"])
                file_id = int(row["file_id"])
                res_id = int(row["res_id"])
                current = files.get(work_id)
                if current is None or rank < current[0]:
                    # (rank, file_id, works_resources.id): la identidad de recurso evita
                    # que dos PDMX con el MISMO título colapsen en una sola reps.
                    files[work_id] = (rank, file_id, res_id)
            # Género(s): `work_genres` + `genres`.
            cur.execute(
                "SELECT wg.works_id AS work_id, g.name AS name, g.id AS genre_id "
                "FROM work_genres wg JOIN genres g ON g.id = wg.genres_id "
                f"WHERE wg.works_id IN ({placeholders}) ORDER BY wg.works_id, g.name",
                ids,
            )
            for row in cur.fetchall():
                work_id = int(row["work_id"])
                name = str(row["name"] or "")
                current = genres.get(work_id)
                genres[work_id] = (
                    (current[0] + "; " + name, current[1]) if current else (name, int(row["genre_id"]))
                )
        for w in works:
            title = str(w.get("title") or "").strip()
            if not title:
                continue
            composer, person_id = composers.get(int(w["id"]), ("", ""))
            if not composer:
                # Obras marcadas en `works` como anónimas/tradicionales: se anuncian así
                # (no son hueco de compositor y no se crea ninguna persona).
                composer = _ATTR_LABELS.get(str(w.get("attr_type") or "").upper(), "")
            file_entry = files.get(int(w["id"]))
            file_id = file_entry[1] if file_entry else None
            res_id = file_entry[2] if file_entry else 0
            genre_names, genre_id = genres.get(int(w["id"]), ("", 0))
            download_url = f"{base}/api/download/{file_id}" if file_id is not None else None
            yield {
                "title": title,
                "composer": composer or None,
                "person_id": person_id or None,
                "catalogue": w.get("catalogue"),
                "year": w.get("year"),
                "instrumentation": w.get("instrumentation"),
                "genre": genre_names or None,
                "genre_id": genre_id,
                "provider": "omr",
                "format": "musicxml",
                "download_url": download_url,
                "available": 1 if file_id is not None else 0,
                "quality": 0,
                # Identidad de recurso (como CPDL): la obra de storage + el resource.
                "source_rep_id": str(int(w["id"])),
                "resource_id": res_id,
            }
            emitted += 1
        last_id = max(ids)
        if limit <= 0 or emitted >= limit:
            return


# --- Voicing CPDL -------------------------------------------------------------------------
# El voicing ES la formación vocal: `ensembles_code` relacionado con la obra en
# `work_ensembles` (osap-storage). El índice lo publica como faceta (`kind='ensemble'`).


def _cpdl_format(rtype: object) -> str | None:
    """Formato de un `works_resources_type` CPDL.

    NO disfraza MUS/SIB/MSCZ de MusicXML: se aceptan como formatos propios, y para
    tipos no servibles devuelve None (se descartan explícitamente).
    """
    return {
        "mxl": "musicxml",
        "musicxml": "musicxml",
        "xml": "musicxml",
        "mid": "midi",
        "midi": "midi",
        "pdf": "pdf",
        "mp3": "audio",
        "audio": "audio",
        "mus": "mus",
        "sib": "sib",
        "mscz": "mscz",
        "capx": "capx",
    }.get(str(rtype or "").strip().lower())


def _iter_cpdl(maestro: pymysql.Connection, from_id: int, limit: int, batch: int = 2000):
    """Obras CPDL del maestro (`works_origin='CPDL'`), sin re-resolver nada.

    - Compositor: rol 1 de `works_person_roles` → `persons` (persona **propia de CPDL**,
      ya resuelta en el maestro).
    - Representación/recurso: `representations` (edición CPDL = `cpdlno`) ⨝
      `works_resources` (por `works_resources_representation_id`). **Una fila de índice
      por resource descargable**, conservando `source_rep_id` (edición) y `resource_id`.
      Una edición sin resources no genera una representación ficticia.
    - Voicing: `ensembles_code` de `work_ensembles` (`kind='ensemble'`).
    """
    last_id = from_id
    emitted = 0
    while limit <= 0 or emitted < limit:
        take = batch if limit <= 0 else min(batch, limit - emitted)
        with maestro.cursor() as cur:
            cur.execute(
                "SELECT id, works_title AS title, works_catalogue AS catalogue, "
                "works_year AS year "
                "FROM works WHERE works_origin='CPDL' AND id > %s ORDER BY id LIMIT %s",
                (last_id, take),
            )
            works = cur.fetchall()
        if not works:
            return
        ids = [w["id"] for w in works]
        ph = ",".join(["%s"] * len(ids))
        composers: dict[int, tuple[str, str]] = {}
        # work_id -> [(format, url, available, source_rep_id, resource_id), ...]
        resources: dict[int, list[tuple[str, str, int, str, int]]] = {}
        canonical: dict[int, list[str]] = {}
        with maestro.cursor() as cur:
            cur.execute(
                "SELECT r.works_person_roles_work_id AS work_id, p.persons_name AS composer, "
                "r.works_person_roles_person_id AS person_id "
                "FROM works_person_roles r JOIN persons p "
                "ON p.persons_id = r.works_person_roles_person_id "
                f"WHERE r.works_person_roles_work_id IN ({ph}) "
                "AND r.works_person_roles_role_id = 1 "
                "ORDER BY r.works_person_roles_work_id, r.works_person_roles_order, "
                "r.works_person_roles_id",
                ids,
            )
            for row in cur.fetchall():
                composers.setdefault(
                    int(row["work_id"]),
                    (str(row["composer"] or ""), str(row["person_id"] or "")),
                )
            cur.execute(
                "SELECT r.representations_works_id AS work_id, "
                "r.id AS rep_id, r.representations_origin_cpdlno AS cpdlno, "
                "wr.id AS res_id, wr.works_resources_type AS rtype, "
                "wr.works_resources_url AS url, wr.works_resources_file_id AS file_id "
                "FROM representations r JOIN works_resources wr "
                "ON wr.works_resources_representation_id = r.id "
                f"WHERE r.representations_works_id IN ({ph})",
                ids,
            )
            for row in cur.fetchall():
                url = str(row["url"] or "")
                fmt = _cpdl_format(row["rtype"])
                if not url or fmt is None:
                    continue  # sin URL o formato no servible: no se inventa una fila
                source_rep_id = str(row["cpdlno"] or row["rep_id"] or "")
                resources.setdefault(int(row["work_id"]), []).append(
                    (
                        fmt,
                        url,
                        1 if row["file_id"] else 0,
                        source_rep_id,
                        int(row["res_id"] or 0),
                    )
                )
            cur.execute(
                "SELECT we.works_id AS work_id, e.ensembles_code AS code "
                "FROM work_ensembles we JOIN ensembles e ON e.id = we.ensembles_id "
                f"WHERE we.works_id IN ({ph})",
                ids,
            )
            for row in cur.fetchall():
                code = str(row["code"] or "").strip()
                if code:
                    canonical.setdefault(int(row["work_id"]), []).append(code.upper())
        for w in works:
            wid = int(w["id"])
            title = str(w.get("title") or "").strip()
            if not title:
                continue
            composer, person_id = composers.get(wid, ("", ""))
            terms: list[tuple[str, str]] = [
                ("ensemble", c) for c in dict.fromkeys(canonical.get(wid, []))
            ]
            for fmt, url, available, source_rep_id, resource_id in resources.get(wid, []):
                yield {
                    "title": title,
                    "composer": composer or None,
                    "person_id": person_id or None,
                    "catalogue": w.get("catalogue"),
                    "year": w.get("year"),
                    "instrumentation": None,
                    "genre": None,
                    "genre_id": 0,
                    "provider": "cpdl",
                    "format": fmt,
                    "download_url": url,
                    "available": available,
                    "quality": 0,
                    "source_rep_id": source_rep_id,
                    "resource_id": resource_id,
                    "voicing_terms": terms,
                }
                emitted += 1
        last_id = max(ids)
        if limit <= 0 or emitted >= limit:
            return


def _iter_imslp(start: int, limit: int, verify_ssl: bool = True):
    """Obras de IMSLP vía Worklist API (lista completa, paginada por `start`)."""
    ctx = None if verify_ssl else ssl._create_unverified_context()  # noqa: S323
    n = 0
    while limit <= 0 or n < limit:
        url = (
            f"{_IMSLP_API}?account=worklist/disclaimer=accepted/sort=id/type=2/"
            f"start={start}/retformat=json"
        )
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:  # noqa: S310
                doc = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001
            print(f"  imslp error start={start}: {exc}", flush=True)
            break
        meta = doc.get("metadata") if isinstance(doc, dict) else None
        more = bool(meta.get("moreresultsavailable")) if isinstance(meta, dict) else False
        keys = [k for k in (doc or {}) if k != "metadata"]
        if not keys:
            break
        for k in keys:
            entry = doc[k]
            if not isinstance(entry, dict):
                continue
            iv = entry.get("intvals") or {}
            title = str(iv.get("worktitle") or "")
            composer = _reverse_last_first(str(iv.get("composer") or "")) or None
            if not title.strip():
                continue
            yield {
                "title": title,
                "composer": composer,
                "person_id": None,
                "catalogue": iv.get("icatno") or None,
                "year": None,
                "instrumentation": None,
                "provider": "imslp",
                "format": "pdf",
                "download_url": entry.get("permlink"),
                "available": 0,
                "quality": 0,
            }
            n += 1
            if limit > 0 and n >= limit:
                return
        if not more:
            break
        start += len(keys)
        time.sleep(0.5)


def _iter_mutopia(start_at: int, limit: int):
    """Catálogo completo de Mutopia (make-table.cgi paginado por `startat`)."""
    n = 0
    page = start_at
    while limit <= 0 or n < limit:
        params = {
            "searchingfor": "",
            "startat": str(page),
            "Composer": "", "Instrument": "", "Style": "", "collection": "",
            "id": "", "solo": "", "recent": "", "timelength": "", "timeunit": "",
            "lilyversion": "", "preview": "",
        }
        url = f"{_MUTOPIA_CGI}?{urllib.parse.urlencode(params)}"
        body = ""
        for attempt in range(3):
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                    body = resp.read().decode("utf-8", "replace")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  mutopia error startat={page} (intento {attempt + 1}): {exc}", flush=True)
                time.sleep(5)
        if not body:
            break
        works = _parse_table(body)
        if not works:
            break
        for w in works:
            resources = w.get("resources") or []
            for res in resources:
                if not isinstance(res, dict):
                    continue
                yield {
                    "title": str(w.get("title") or ""),
                    "composer": w.get("composer"),
                    "person_id": None,
                    "catalogue": None,
                    "year": None,
                    "instrumentation": None,
                    "provider": "mutopia",
                    "format": str(res.get("format") or "pdf"),
                    "download_url": res.get("download_url"),
                    "available": 1 if res.get("available") else 0,
                    "quality": 0,
                }
                n += 1
                if limit > 0 and n >= limit:
                    return
        m = re.search(r'make-table\.cgi\?startat=(\d+)&', body)
        nxt = int(m.group(1)) if m else None
        if nxt is None or nxt <= page:
            break
        page = nxt
        time.sleep(0.4)


def _iter_musicbrainz(dump_dir: str, art_only: bool, limit: int):
    """Obras con relación composer del dump local de MusicBrainz (mbdump)."""
    import os

    base = dump_dir.rstrip("/\\")

    def open_table(name: str):
        path = os.path.join(base, name)
        if not os.path.exists(path):
            return None
        return open(path, encoding="utf-8", errors="replace")

    # 1) composer links (link_type 168 = artist compone work).
    composer_links: set[str] = set()
    fh = open_table("link")
    if fh is None:
        print("  musicbrainz: no se encontró el fichero 'link' del dump", flush=True)
        return
    with fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 2 and cols[1] == _MB_COMPOSER_LINK_TYPE:
                composer_links.add(cols[0])
    print(f"  musicbrainz: {len(composer_links)} composer links", flush=True)

    # 2) works: id -> (gid, name, type). Filtro por tipo (art vs todo).
    fh = open_table("work")
    if fh is None:
        print("  musicbrainz: no se encontró el fichero 'work' del dump", flush=True)
        return
    works: dict[str, tuple[str, str, str]] = {}
    with fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 4:
                continue
            wt = cols[3]
            if art_only and wt not in _MB_ART_TYPES:
                continue
            works[cols[0]] = (cols[1], cols[2], wt)
    print(f"  musicbrainz: {len(works)} obras (art={art_only})", flush=True)

    # 3) l_artist_work: work_id -> set(artist_id) para composer links.
    fh = open_table("l_artist_work")
    if fh is None:
        print("  musicbrainz: no se encontró el fichero 'l_artist_work' del dump", flush=True)
        return
    work_artists: dict[str, set[str]] = {}
    with fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 4 or cols[1] not in composer_links:
                continue
            if cols[3] in works:
                work_artists.setdefault(cols[3], set()).add(cols[2])
    print(f"  musicbrainz: {len(work_artists)} obras con compositor", flush=True)

    # 4) artist names (solo los necesarios).
    needed: set[str] = set()
    for artists in work_artists.values():
        needed.update(artists)
    fh = open_table("artist")
    if fh is None:
        print("  musicbrainz: no se encontró el fichero 'artist' del dump", flush=True)
        return
    artist_names: dict[str, str] = {}
    with fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 3 and cols[0] in needed:
                artist_names[cols[0]] = cols[2]
    print(f"  musicbrainz: {len(artist_names)} compositores con nombre", flush=True)

    n = 0
    for wid, artists in work_artists.items():
        if wid not in works:
            continue
        gid, name, _wt = works[wid]
        composers = "; ".join(
            artist_names.get(a, "") for a in sorted(artists) if artist_names.get(a)
        ) or None
        if not composers:
            continue
        yield {
            "title": name,
            "composer": composers,
            "person_id": None,
            "catalogue": None,
            "year": None,
            "instrumentation": None,
            "provider": "musicbrainz",
            "format": "json",
            "download_url": f"https://musicbrainz.org/work/{gid}" if gid else None,
            "available": 0,
            "quality": 0,
        }
        n += 1
        if limit > 0 and n >= limit:
            return


# ---------------------------------------------------------------- ingest


def _ingest_page(
    api: pymysql.Connection,
    maestro: pymysql.Connection | None,
    work_list: list[dict],
    resolver_cache: dict[str, tuple[str | None, str | None]],
    anchors_cache: dict[str, list[dict]],
    catalogue_cache: dict[str, list[dict]],
) -> tuple[int, int, int]:
    """Ingest por LOTES de una página de obras (un solo escritor).

    Misma semántica que `_ingest` (identidad por catálogo → anclaje → (title_key, composer)),
    pero sin consultas por obra: los candidatos de catálogo/anclaje se cachean por compositor
    y el look-up/inserción/actualización se hacen por lotes. Devuelve (nuevas, actualizadas,
    omitidas).
    """
    prepared: list[dict] = []
    for work in work_list:
        title = str(work.get("title") or "").strip()
        if not title:
            continue
        record = dict(work)
        record["title"] = title
        record["tk"] = title_key(title)[:255]
        composer_raw = str(work.get("composer") or "").strip()
        person_id = work.get("person_id")
        composer_name = composer_raw or None
        if person_id and person_id in _PERSON_ID_CANON:
            person_id, canon_name = _PERSON_ID_CANON[person_id]
            if canon_name:
                composer_name = canon_name
        if not person_id and composer_name and maestro is not None:
            person_id, canonical = _resolve_person(maestro, composer_name, resolver_cache)
            if canonical:
                composer_name = canonical
        record["composer_name"] = composer_name[:255] if composer_name else None
        record["person_id"] = person_id
        # Tokens significativos del título (excluido el compositor, que en PDMX va dentro
        # del título). Se calculan UNA vez por obra: comparar contra hasta 500 anclas
        # normalizando texto cada vez era el cuello del rebuild.
        record["tokens"] = _significant_tokens(title, record["composer_name"])
        catalogue_raw = work.get("catalogue") or _extract_composer_catalogue(title)
        record["catalogue_raw"] = catalogue_raw
        record["cat_key"] = _catalogue_key(catalogue_raw)
        record["cat_identity"] = _canonical_catalogue_identity(catalogue_raw)
        year = work.get("year")
        record["year_int"] = int(year) if str(year or "").isdigit() else None
        prepared.append(record)
    if not prepared:
        return 0, 0, 0

    def composer_key(record: dict) -> str | None:
        if record.get("composer_name"):
            return f"c:{record['composer_name']}"
        if record.get("person_id"):
            return f"i:{record['person_id']}"
        return None

    inserted = updated = skipped = 0
    with api.cursor() as cur:
        # 1) Prefetch de las filas existentes de la página por title_key (1 consulta por lote).
        tks = sorted({r["tk"] for r in prepared})
        existing: dict[tuple[str, str], dict] = {}
        for start in range(0, len(tks), 500):
            chunk = tks[start : start + 500]
            placeholders = ",".join(["%s"] * len(chunk))
            cur.execute(
                "SELECT id, title_key, person_id, composer_name FROM index_works "
                f"WHERE title_key IN ({placeholders})",
                chunk,
            )
            for row in cur.fetchall():
                existing[
                    (str(row["title_key"]), str(row["person_id"] or ""))
                ] = row
                if row["composer_name"]:
                    existing[
                        (str(row["title_key"]), f"name:{row['composer_name']}")
                    ] = row

        # 2) Resolución de identidad (catálogo único → anclaje) con caché por compositor.
        resolved: list[tuple[dict, dict | None]] = []
        for record in prepared:
            key = composer_key(record)
            row: dict | None = None
            if (
                record["cat_identity"]
                and _is_unique_catalogue(record["cat_identity"])
                and key is not None
            ):
                if key not in catalogue_cache:
                    if record.get("composer_name"):
                        cur.execute(
                            "SELECT id, title, catalogue FROM index_works WHERE composer_name=%s "
                            "AND catalogue IS NOT NULL ORDER BY id LIMIT 200",
                            (record["composer_name"],),
                        )
                    else:
                        cur.execute(
                            "SELECT id, title, catalogue FROM index_works WHERE person_id=%s "
                            "AND catalogue IS NOT NULL ORDER BY id LIMIT 200",
                            (record["person_id"],),
                        )
                    catalogue_cache[key] = [
                        (
                            int(candidate["id"]),
                            _canonical_catalogue_identity(str(candidate.get("catalogue") or "")),
                            _significant_tokens(
                                str(candidate.get("title") or ""), record["composer_name"]
                            ),
                        )
                        for candidate in cur.fetchall()
                    ]
                for cand_id, cand_identity, cand_tokens in catalogue_cache[key]:
                    if cand_identity == record["cat_identity"] and (record["tokens"] & cand_tokens):
                        row = {"id": cand_id}
                        break
            if row is None and key is not None:
                if key not in anchors_cache:
                    if record.get("composer_name"):
                        cur.execute(
                            "SELECT id, title FROM index_works WHERE composer_name=%s "
                            "AND catalogue IS NOT NULL AND catalogue <> '' ORDER BY id LIMIT 500",
                            (record["composer_name"],),
                        )
                    else:
                        cur.execute(
                            "SELECT id, title FROM index_works WHERE person_id=%s "
                            "AND catalogue IS NOT NULL AND catalogue <> '' ORDER BY id LIMIT 500",
                            (record["person_id"],),
                        )
                    anchors_cache[key] = [
                        (
                            int(anchor["id"]),
                            _significant_tokens(
                                str(anchor.get("title") or ""), record["composer_name"]
                            ),
                        )
                        for anchor in cur.fetchall()
                    ]
                for anchor_id, anchor_tokens in anchors_cache[key]:
                    if _tokens_subset_sets(record["tokens"], anchor_tokens):
                        row = {"id": anchor_id}
                        break
            resolved.append((record, row))

        # 3) Look-up FUERTE por (title_key, person_id/composer_name) usando el prefetch.
        #    `strong` distingue identidad fuerte (title_key + persona) de match difuso
        #    (catálogo/anclaje): en difuso NO se muta title/title_key/catalogue.
        pending: list[tuple[dict, dict | None, bool]] = []
        for record, row in resolved:
            strong = False
            if row is None:
                cid = str(record.get("person_id") or "")
                row = existing.get((record["tk"], cid))
                if row is None and record.get("composer_name"):
                    row = existing.get((record["tk"], f"name:{record['composer_name']}"))
                strong = row is not None
            pending.append((record, row, strong))

        # 4) Insert/UPDATE por lotes (deduplicando en página por la clave única).
        seen_page: set[tuple[str, str]] = set()
        inserts: list[tuple] = []
        updates: list[tuple] = []
        ids_by_record: dict[int, int] = {}
        for index, (record, row, strong) in enumerate(pending):
            if row is not None:
                if strong:
                    updates.append(
                        (
                            record["title"][:1024],
                            record["composer_name"],
                            record["catalogue_raw"],
                            record["cat_key"],
                            record["year_int"],
                            record.get("instrumentation") or None,
                            int(record["genre_id"]) if record.get("genre_id") is not None else None,
                            int(row["id"]),
                        )
                    )
                # Match difuso: se CONSERVA la identidad de la obra (title/title_key/
                # catalogue intactos); solo se le adjunta la representación.
                ids_by_record[index] = int(row["id"])
                updated += 1
                continue
            dedupe_key = (record["tk"], str(record.get("person_id") or ""))
            if dedupe_key in seen_page:
                skipped += 1
                continue
            seen_page.add(dedupe_key)
            inserts.append(
                (
                    record["title"][:1024],
                    record["tk"],
                    record["composer_name"],
                    record.get("person_id"),
                    record["catalogue_raw"],
                    record["cat_key"],
                    record["year_int"],
                    record.get("instrumentation") or None,
                    int(record["genre_id"]) if record.get("genre_id") is not None else None,
                )
            )
            ids_by_record[index] = -len(inserts)  # provisional (negativo = índice de insert)
            inserted += 1
        if updates:
            cur.executemany(
                "UPDATE index_works SET title=%s, composer_name=%s, catalogue=%s, "
                "catalogue_key=%s, year=%s, instrumentation=%s, genre_id=%s, updated_at=NOW() "
                "WHERE id=%s",
                updates,
            )
        if inserts:
            cur.executemany(
                "INSERT INTO index_works (title, title_key, composer_name, person_id, "
                "catalogue, catalogue_key, year, instrumentation, genre_id, source_count, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,NOW())",
                inserts,
            )
            # Ids de lo insertado: 1 consulta por lote usando los title_key de la página.
            insert_tks = sorted({record["tk"] for index, (record, _row, _strong) in enumerate(pending)
                                 if ids_by_record.get(index, 0) < 0})
            fresh: dict[tuple[str, str], int] = {}
            for start in range(0, len(insert_tks), 500):
                chunk = insert_tks[start : start + 500]
                placeholders = ",".join(["%s"] * len(chunk))
                cur.execute(
                    "SELECT id, title_key, person_id FROM index_works "
                    f"WHERE title_key IN ({placeholders})",
                    chunk,
                )
                for row in cur.fetchall():
                    fresh[(str(row["title_key"]), str(row["person_id"] or ""))] = int(row["id"])
            for index, (record, _row, _strong) in enumerate(pending):
                provisional = ids_by_record.get(index)
                if provisional is not None and provisional < 0:
                    ids_by_record[index] = fresh.get(
                        (record["tk"], str(record.get("person_id") or "")), 0
                    )

        # 5) Representaciones por lotes.
        rep_rows: list[tuple] = []
        for index, (record, _row, _strong) in enumerate(pending):
            work_id = ids_by_record.get(index)
            if not work_id or work_id <= 0:
                continue
            rep_rows.append(
                (
                    work_id,
                    str(record.get("provider") or "omr"),
                    str(record.get("source_rep_id") or ""),
                    int(record.get("resource_id") or 0),
                    str(record.get("format") or "musicxml"),
                    record.get("download_url"),
                    record["title"][:1024],
                    int(record.get("available", 0)),
                    int(record.get("quality", 0)),
                )
            )
        if rep_rows:
            cur.executemany(
                "INSERT INTO index_representations (work_id, provider, source_rep_id, resource_id, "
                "format, download_url, title_provider, available, quality) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE download_url=VALUES(download_url), "
                "available=VALUES(available), quality=VALUES(quality)",
                rep_rows,
            )
    return inserted, updated, skipped


def _ingest(
    api: pymysql.Connection,
    maestro: pymysql.Connection | None,
    work: dict,
    resolver_cache: dict[str, tuple[str | None, str | None]],
    anchors_cache: dict[str, list[dict]] | None = None,
) -> tuple[str, str]:
    """Upsert de una obra en index_works + index_representations. Devuelve (estado, detalle)."""
    title = str(work.get("title") or "").strip()
    if not title:
        return "skip", "sin título"
    composer_raw = str(work.get("composer") or "").strip()
    person_id = work.get("person_id")
    composer_name = composer_raw or None
    if person_id and person_id in _PERSON_ID_CANON:
        person_id, canon_name = _PERSON_ID_CANON[person_id]
        if canon_name:
            composer_name = canon_name
    if not person_id and composer_name and maestro is not None:
        person_id, canonical = _resolve_person(maestro, composer_name, resolver_cache)
        if canonical:
            composer_name = canonical
    if composer_name:
        composer_name = composer_name[:255]

    tk = title_key(title)[:255]
    catalogue_raw = work.get("catalogue")
    if not catalogue_raw:
        catalogue_raw = _extract_composer_catalogue(title)
    cat_key = _catalogue_key(catalogue_raw)
    # Identidad fina: el catálogo COMPLETO normalizado (p. ej. "op 10 no 9" -> "op10no9"),
    # no solo el prefijo+serie (que uniría obras distintas de una misma serie).
    cat_identity = _canonical_catalogue_identity(catalogue_raw)
    year = work.get("year")
    year_int = int(year) if str(year or "").isdigit() else None

    provider = str(work.get("provider") or "omr")
    fmt = str(work.get("format") or "musicxml")
    with api.cursor() as cur:
        row = None
        # `strong` = identidad FUERTE (title_key + persona). Los matches por catálogo o
        # anclaje son difusos: NO pueden mutar title/title_key/catalogue de la obra.
        strong = False
        # Identidad por catálogo completo: solo si el catálogo identifica una ÚNICA obra
        # (K.618 sí; "TWV 55" es serie y no basta) + compositor + palabra significativa.
        if cat_identity and _is_unique_catalogue(cat_identity):
            if composer_name:
                cur.execute(
                    "SELECT id, title, catalogue FROM index_works WHERE composer_name=%s "
                    "AND catalogue IS NOT NULL ORDER BY id LIMIT 200",
                    (composer_name,),
                )
            elif person_id:
                cur.execute(
                    "SELECT id, title, catalogue FROM index_works WHERE person_id=%s "
                    "AND catalogue IS NOT NULL ORDER BY id LIMIT 200",
                    (person_id,),
                )
            else:
                cur.execute("SELECT id, title, catalogue FROM index_works WHERE 1=0")
            for candidate in cur.fetchall():
                if (
                    _canonical_catalogue_identity(str(candidate.get("catalogue") or "")) == cat_identity
                    and _shares_significant_token(title, str(candidate.get("title") or ""), composer_name)
                ):
                    row = candidate
                    break
        if row is None and (person_id or composer_name):
            # El anclaje por título consulta hasta 500 obras del compositor: se cachea por
            # compositor (si no, era una consulta de 500 filas POR OBRA → horas de rebuild).
            cache_key = f"c:{composer_name}" if composer_name else f"i:{person_id}"
            anchors = anchors_cache.get(cache_key) if anchors_cache is not None else None
            if anchors is None:
                if composer_name:
                    cur.execute(
                        "SELECT id, title FROM index_works WHERE composer_name=%s "
                        "AND catalogue IS NOT NULL AND catalogue <> '' ORDER BY id LIMIT 500",
                        (composer_name,),
                    )
                else:
                    cur.execute(
                        "SELECT id, title FROM index_works WHERE person_id=%s "
                        "AND catalogue IS NOT NULL AND catalogue <> '' ORDER BY id LIMIT 500",
                        (person_id,),
                    )
                anchors = list(cur.fetchall())
                if anchors_cache is not None:
                    anchors_cache[cache_key] = anchors
            for anchor in anchors:
                if _tokens_subset(title, str(anchor.get("title") or ""), composer_name):
                    row = anchor
                    break
        if row is None:
            # El look-up debe coincidir con la clave única (title_key, person_id): si se
            # busca por composer_name, dos grafías del mismo compositor insertarían duplicado.
            if person_id:
                cur.execute(
                    "SELECT id, title FROM index_works WHERE title_key=%s AND person_id=%s",
                    (tk, person_id),
                )
                row = cur.fetchone()
            if row is None and composer_name:
                cur.execute(
                    "SELECT id, title FROM index_works WHERE title_key=%s AND composer_name=%s",
                    (tk, composer_name),
                )
                row = cur.fetchone()
            if row is None and not person_id and not composer_name:
                cur.execute(
                    "SELECT id, title FROM index_works WHERE title_key=%s AND person_id IS NULL",
                    (tk,),
                )
                row = cur.fetchone()
            strong = row is not None
        if row is None:
            try:
                cur.execute(
                    "INSERT INTO index_works (title, title_key, composer_name, person_id, "
                    "catalogue, catalogue_key, year, instrumentation, genre_id, source_count, updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,NOW())",
                    (title[:1024], tk, composer_name, person_id,
                     catalogue_raw, cat_key, year_int,
                     (work.get("instrumentation") or None),
                     (int(work["genre_id"]) if work.get("genre_id") is not None else None)),
                )
                work_id = cur.lastrowid
            except pymysql.err.IntegrityError:
                # Carrera/legado con clave truncada: se reutiliza la fila existente.
                cur.execute(
                    "SELECT id, title FROM index_works WHERE title_key=%s AND person_id <=> %s",
                    (tk, person_id),
                )
                existing = cur.fetchone()
                if existing is None:
                    raise
                work_id = int(existing["id"])
        else:
            work_id = row["id"]
            # Solo el match FUERTE actualiza la identidad de la obra. Un match difuso
            # (catálogo/anclaje) NO toca title/title_key/catalogue: así un falso positivo
            # no puede contaminar la obra (el bug de los "cubos" de OMR).
            if strong:
                cur.execute(
                    "UPDATE index_works SET title=%s, composer_name=%s, "
                    "catalogue=%s, catalogue_key=%s, year=%s, "
                    "instrumentation=%s, genre_id=%s, updated_at=NOW() "
                    "WHERE id=%s",
                    (title[:1024], composer_name, catalogue_raw,
                     cat_key, year_int, (work.get("instrumentation") or None),
                     (int(work["genre_id"]) if work.get("genre_id") is not None else None),
                     work_id),
                )
        cur.execute(
            "INSERT INTO index_representations (work_id, provider, source_rep_id, resource_id, "
            "format, download_url, title_provider, available, quality) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE download_url=VALUES(download_url), "
            "available=VALUES(available), quality=VALUES(quality)",
            (work_id, provider, str(work.get("source_rep_id") or ""),
             int(work.get("resource_id") or 0), fmt, work.get("download_url"), title[:1024],
             int(work.get("available", 0)), int(work.get("quality", 0))),
        )
        # Voicing (faceta): el voicing ES la formación vocal (`ensembles_code`). Se
        # reemplazan las filas del work para no arrastrar un reindexado anterior.
        voicing_terms = work.get("voicing_terms") or []
        cur.execute("DELETE FROM index_work_voicings WHERE work_id = %s", (work_id,))
        if voicing_terms:
            cur.executemany(
                "INSERT INTO index_work_voicings (work_id, kind, term) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE term=VALUES(term)",
                [
                    (work_id, str(kind)[:16], str(term)[:64])
                    for kind, term in voicing_terms
                ],
            )
    return "ok", f"{provider}/{fmt}"


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--providers", default="omr",
        help="proveedores a indexar (coma): omr,imslp,mutopia,musicbrainz"
    )
    parser.add_argument("--limit", type=int, default=0,
                        help="límite de obras por proveedor (0 = todas)")
    parser.add_argument("--from-id", type=int, default=0, help="OMR: reanudar desde este id")
    parser.add_argument("--imslp-start", type=int, default=0, help="IMSLP: reanudar en este start")
    parser.add_argument("--imslp-verify-ssl", action="store_true",
                        help="IMSLP: verificar SSL (por defecto NO, certificado caducado)")
    parser.add_argument("--mutopia-start-at", type=int, default=0, help="Mutopia: página inicial")
    parser.add_argument("--mb-dump", default=None, help="MusicBrainz: directorio mbdump")
    parser.add_argument("--mb-types", choices=("art", "all"), default="art",
                        help="MusicBrainz: solo tipos de música artística (art) o todas (all)")
    parser.add_argument("--omr-base-url", default="http://127.0.0.1:8000",
                        help="OMR: base de storage para download_url (/api/download/{id})")
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="2027osapdb")
    parser.add_argument("--db-api", default="osap-api")
    parser.add_argument("--dry-run", action="store_true",
                        help="Recorre y valida sin escribir en el índice.")
    parser.add_argument("--db-omr", default="osap-storage")
    args = parser.parse_args()

    api_db = {
        "host": args.db_host, "user": args.db_user, "password": args.db_password,
        "database": args.db_api, "charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor,
    }
    omr_db = {
        "host": args.db_host, "user": args.db_user, "password": args.db_password,
        "database": args.db_omr, "charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor,
    }

    api = pymysql.connect(**api_db)
    omr = pymysql.connect(**omr_db)
    maestro = omr
    _load_person_canon(maestro)
    resolver_cache: dict[str, tuple[str | None, str | None]] = {}
    anchors_cache: dict[str, list[dict]] = {}
    catalogue_cache: dict[str, list[dict]] = {}
    try:
        for provider in [p.strip() for p in args.providers.split(",") if p.strip()]:
            t0 = time.time()
            inserted = updated = skipped = 0
            print(f"=== INDEX {provider} ===", flush=True)
            if provider == "omr":
                rows = _iter_omr(omr, args.from_id, args.limit or 2_000_000,
                                 args.omr_base_url)
            elif provider == "imslp":
                rows = _iter_imslp(args.imslp_start, args.limit, verify_ssl=args.imslp_verify_ssl)
            elif provider == "mutopia":
                rows = _iter_mutopia(args.mutopia_start_at, args.limit)
            elif provider == "musicbrainz":
                if not args.mb_dump:
                    print("  error: --mb-dump es obligatorio para musicbrainz", flush=True)
                    continue
                rows = _iter_musicbrainz(args.mb_dump, args.mb_types == "art", args.limit)
            elif provider == "cpdl":
                rows = _iter_cpdl(maestro, args.from_id, args.limit or 2_000_000)
            else:
                print(f"  proveedor desconocido: {provider}", flush=True)
                continue

            # OMR: ingest por LOTES (mismo resultado, sin consultas por obra). El resto de
            # proveedores siguen con el ingest por obra.
            page: list[dict] = []
            for w in rows:
                page.append(w)
                if len(page) >= 1000:
                    if args.dry_run:
                        skipped += len(page)
                    elif provider == "omr":
                        ins, upd, skp = _ingest_page(
                            api, maestro, page, resolver_cache, anchors_cache, catalogue_cache
                        )
                        inserted += ins
                        updated += upd
                        skipped += skp
                    else:
                        for item in page:
                            status, _detail = _ingest(api, maestro, item, resolver_cache, anchors_cache)
                            if status == "ok":
                                inserted += 1
                            elif status == "skip":
                                skipped += 1
                            else:
                                updated += 1
                    page = []
                    api.commit()
                    if (inserted + skipped + updated) % 5000 < 1000:
                        print(
                            f"  ... {inserted + skipped + updated} obras "
                            f"(nuevas={inserted} actualizadas={updated} omitidas={skipped})",
                            flush=True,
                        )
            if page:
                if args.dry_run:
                    skipped += len(page)
                elif provider == "omr":
                    ins, upd, skp = _ingest_page(
                        api, maestro, page, resolver_cache, anchors_cache, catalogue_cache
                    )
                    inserted += ins
                    updated += upd
                    skipped += skp
                else:
                    for item in page:
                        status, _detail = _ingest(api, maestro, item, resolver_cache, anchors_cache)
                        if status == "ok":
                            inserted += 1
                        elif status == "skip":
                            skipped += 1
                        else:
                            updated += 1
            api.commit()
            elapsed = time.time() - t0
            print(f"  obras: insertadas={inserted} errores={updated} omitidas={skipped} "
                  f"({elapsed:.1f}s)", flush=True)
        print("=== RESUMEN ===")
        with api.cursor() as cur:
            cur.execute(
                "UPDATE index_works w SET w.source_count = ("
                "SELECT COUNT(DISTINCT provider) FROM index_representations r "
                "WHERE r.work_id = w.id)"
            )
            api.commit()
            cur.execute("SELECT COUNT(*) AS n FROM index_works")
            print(f"  total index_works: {cur.fetchone()['n']}")
            cur.execute("SELECT COUNT(*) AS n FROM index_representations")
            print(f"  total index_representations: {cur.fetchone()['n']}")
            cur.execute("SELECT provider, COUNT(*) AS n FROM index_representations "
                        "GROUP BY provider ORDER BY n DESC")
            for r in cur.fetchall():
                print(f"    {r['provider']:14}: {r['n']}")
    finally:
        api.close()
        omr.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
