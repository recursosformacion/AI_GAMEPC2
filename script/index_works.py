#!/usr/bin/env python
"""Indexador local de obras — multi-proveedor (paso 1 del índice).

Lee obras de varios proveedores y puebla el índice local
(`index_works` + `index_representations` en la BD de osap-api), normalizando títulos
(`title_key`) y compositores (canonical + `composer_id` del Maestro) y deduplicando por
(`title_key`, `composer_id`). La normalización es determinista: el índice GUARDA el
resultado, no lo recalcula por búsqueda.

Proveedores (selección con `--providers`):
  omr          -> corpus OMR (osap-storage.works)                          [musicxml]
  imslp        -> Worklist API de IMSLP (paginada por start)               [pdf/página]
  mutopia      -> make-table.cgi (listing completo, paginado por startat)  [pdf+midi]
  musicbrainz  -> dump local mbdump (work + l_artist_work + artist)        [metadata]

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


def _resolve_composer_id(
    conn: pymysql.Connection, composer_name: str | None, cache: dict[str, str]
) -> str | None:
    """Resuelve un nombre de compositor contra el Maestro (osap-storage) por name_key."""
    if not composer_name or _is_anon(composer_name):
        return None
    key = composer_key(composer_name)
    if key in cache:
        return cache[key] or None
    cid: str | None = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.id FROM composers c "
                "LEFT JOIN composer_aliases a ON a.composer_id=c.id "
                "WHERE c.status != 'merged' AND (c.name=%s OR a.normalized_alias=%s) "
                "LIMIT 1",
                (composer_name, key),
            )
            row = cur.fetchone()
            if row:
                cid = row["id"]
    except pymysql.err.ProgrammingError:
        cid = None
    cache[key] = cid or ""
    return cid


# ---------------------------------------------------------------- providers


def _iter_omr(omr: pymysql.Connection, from_id: int, limit: int, storage_base: str, batch: int = 2000):
    """Obras del corpus OMR (tabla works de osap-storage).

    Construye `download_url` como ``{storage_base}/api/download/{file_id}`` (el endpoint
    de storage redirige 302 al CDN/R2) y marca `available=1` cuando hay fichero.
    Pagina por PK y consulta `archive_entries.file_id` por lote (el JOIN completo hace
    filesort de 254k filas).
    """
    base = storage_base.rstrip("/")
    last_id = from_id
    emitted = 0
    while limit <= 0 or emitted < limit:
        take = batch if limit <= 0 else min(batch, limit - emitted)
        with omr.cursor() as cur:
            cur.execute(
                "SELECT id, title, composer, composer_id, catalogue, year, "
                "instrumentation, relative_path, genre "
                "FROM works WHERE id > %s ORDER BY id LIMIT %s",
                (last_id, take),
            )
            works = cur.fetchall()
        if not works:
            return
        ids = [w["id"] for w in works]
        file_ids: dict[int, int] = {}
        with omr.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(
                "SELECT work_id, file_id FROM archive_entries "
                f"WHERE work_id IN ({placeholders}) AND file_id IS NOT NULL",
                ids,
            )
            for e in cur.fetchall():
                file_ids[e["work_id"]] = e["file_id"]
        for w in works:
            title = str(w.get("title") or "")
            if not title.strip():
                continue
            file_id = file_ids.get(int(w["id"]))
            download_url = f"{base}/api/download/{file_id}" if file_id is not None else None
            yield {
                "title": title,
                "composer": w.get("composer"),
                "composer_id": w.get("composer_id"),
                "catalogue": w.get("catalogue"),
                "year": w.get("year"),
                "instrumentation": w.get("instrumentation"),
                "provider": "omr",
                "format": "musicxml",
                "download_url": download_url,
                "available": 1 if file_id is not None else 0,
                "quality": 0,
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
                "composer_id": None,
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
                    "composer_id": None,
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
            "composer_id": None,
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


def _ingest(
    api: pymysql.Connection,
    maestro: pymysql.Connection | None,
    work: dict,
    resolver_cache: dict[str, str],
) -> tuple[str, str]:
    """Upsert de una obra en index_works + index_representations. Devuelve (estado, detalle)."""
    title = str(work.get("title") or "").strip()
    if not title:
        return "skip", "sin título"
    composer_raw = work.get("composer")
    composer_name = (
        _NORMALIZER.canonical_composer(composer_raw) if composer_raw else None
    )
    if composer_name:
        composer_name = composer_name[:255]
    composer_id = work.get("composer_id")
    if not composer_id and composer_name and maestro is not None:
        composer_id = _resolve_composer_id(maestro, composer_name, resolver_cache)

    tk = title_key(title)[:255]
    catalogue_raw = work.get("catalogue")
    if not catalogue_raw:
        catalogue_raw = _extract_composer_catalogue(title)
    cat_key = _catalogue_key(catalogue_raw)
    year = work.get("year")
    year_int = int(year) if str(year or "").isdigit() else None

    provider = str(work.get("provider") or "omr")
    fmt = str(work.get("format") or "musicxml")
    with api.cursor() as cur:
        if composer_id:
            cur.execute(
                "SELECT id FROM index_works WHERE title_key=%s AND composer_id=%s",
                (tk, composer_id),
            )
        else:
            cur.execute(
                "SELECT id FROM index_works WHERE title_key=%s AND composer_id IS NULL",
                (tk,),
            )
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO index_works (title, title_key, composer_name, composer_id, "
                "catalogue, catalogue_key, year, instrumentation, source_count, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,NOW())",
                (title[:1024], tk, composer_name, composer_id,
                 catalogue_raw, cat_key, year_int,
                 (work.get("instrumentation") or None)),
            )
            work_id = cur.lastrowid
        else:
            work_id = row["id"]
            cur.execute(
                "UPDATE index_works SET title=%s, composer_name=%s, "
                "catalogue=%s, catalogue_key=%s, year=%s, "
                "instrumentation=%s, updated_at=NOW() "
                "WHERE id=%s",
                (title[:1024], composer_name, catalogue_raw,
                 cat_key, year_int, (work.get("instrumentation") or None), work_id),
            )
        cur.execute(
            "INSERT INTO index_representations (work_id, provider, format, "
            "download_url, title_provider, available, quality) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE download_url=VALUES(download_url), "
            "available=VALUES(available), quality=VALUES(quality)",
            (work_id, provider, fmt, work.get("download_url"), title[:1024],
             int(work.get("available", 0)), int(work.get("quality", 0))),
        )
    return "ok", f"{provider}/{fmt}"


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", default="omr",
                        help="proveedores a indexar (coma): omr,imslp,mutopia,musicbrainz")
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
    resolver_cache: dict[str, str] = {}
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
            else:
                print(f"  proveedor desconocido: {provider}", flush=True)
                continue

            for w in rows:
                status, detail = _ingest(api, maestro, w, resolver_cache)
                if status == "ok":
                    inserted += 1
                elif status == "skip":
                    skipped += 1
                else:
                    updated += 1
                if (inserted + skipped + updated) % 1000 == 0:
                    api.commit()
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
