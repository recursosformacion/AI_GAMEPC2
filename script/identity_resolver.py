#!/usr/bin/env python
"""Resolver de identidad escalonado (evidencia acumulada) sobre obras de osap-storage.

Cada fuente aporta EVIDENCIA, no una decisión independiente; la decisión es acumulativa
(no fail-fast). Persiste la decisión + evidencia en BD (composer_identity_resolution). Sin JSONL.

Orden de fuentes (capa que decide / cero red cuando es local):
  0. cache por compositor (nombre normalizado) -> reutiliza exactamente el mismo resultado
  1. Anonymous / NA / etc.                     -> not_applicable
  2. Maestro (composers por nombre/alias)      -> matched_existing
  3. Autoridad local (composer_authority)      -> resuelve local si VIAF/QID inequívoco
  4. Open (Wikidata+MusicBrainz) composer_identifiers() -> ISNI/VIAF/MBID/LCCN/QID
  5. VIAF (identificador + variantes)

Timeouts agresivos por fuente; si una fuente tarda demasiado se registra en la evidencia
y se continúa con las demás. Si wbsearchentities no da QID, no se lanza SPARQL.

Métricas clave: compositores únicos / obras (cache). La pasada de 254k resuelve ~únicos
identidades y asocia las obras reutilizando la cache.

Uso:
    python script/identity_resolver.py [--limit 100] [--from-id 0] [--named-only] [--test t]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutTimeout
from datetime import UTC, datetime
from threading import Lock
from threading import local as _thread_local

import pymysql

from src.osap.infrastructure.identifiers.open_sources import composer_identifiers

_UA = "osap-identity-resolver/0.1"
_NET_TIMEOUT = 8          # s por llamada de red
_WALL_TIMEOUT = 14        # s máx. que esperamos por fuente (hilo)
_EXEC = ThreadPoolExecutor(max_workers=16)

_ANON = {
    "anon", "anon.", "anonymous", "trad", "trad.", "traditional", "attrib.", "attributed",
    "attrib", "unknown", "author unknown", "urheber unbekannt", "urheber unbek.",
    "na", "n/a", "n.a.", "none", "composer",
}


def composer_key(raw: str) -> str:
    """Clave de identidad por nombre normalizado.

    Fusiona variantes de la misma persona: separa los tokens por cualquier no-letra
    (J.S.Skinner = J. Scott Skinner = James Scott Skinner -> 'js skinner'), reduce los
    nombres de pila a su inicial (Wolfgang Amadeus = W. A. -> 'wa mozart') y une la
    partícula irlandesa O' (O'Carolan / O Carolan -> 'ocarolan').
    """
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


def _is_anon(name: str) -> bool:
    low = re.sub(r"[?¿¡!.]+\s*$", "", (name or "").strip().lower())
    return low in _ANON or low.startswith("urheber unbekannt")


def _call(fn, timeout: int):
    fut = _EXEC.submit(fn)
    try:
        return fut.result(timeout=timeout), False
    except _FutTimeout:
        return None, True


class IdentityResolver:
    def __init__(self, db: dict) -> None:
        self._db = db
        self._cache: dict[str, tuple[str, str, dict, str]] = {}
        self._lock = Lock()
        self._local = _thread_local()  # una conexión por hilo, reutilizable
        self.wikidata_calls = 0
        self.viaf_calls = 0
        self.timeouts = 0

    def _conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = pymysql.connect(**self._db)
            self._local.conn = conn
        try:
            conn.ping(reconnect=True)
        except Exception:  # noqa: BLE001
            conn = pymysql.connect(**self._db)
            self._local.conn = conn
        return conn

    # --- fuentes locales (cero red) ---

    def _maestro(self, name: str) -> dict | None:
        conn = self._conn()
        with conn.cursor() as cur:
            key = composer_key(name)
            cur.execute(
                "SELECT c.id, c.name, c.status FROM composers c "
                "LEFT JOIN composer_aliases a ON a.composer_id=c.id "
                "WHERE c.name=%s OR a.normalized_alias=%s LIMIT 1", (name, key))
            row = cur.fetchone()
            if not row:
                return None
            cid = row["id"]
            ids: dict[str, str] = {}
            try:
                cur.execute(
                    "SELECT scheme, value FROM authority_identifiers "
                    "WHERE entity_type='composer' AND entity_id=%s", (cid,))
                ids = {r["scheme"]: r["value"] for r in cur.fetchall()}
            except pymysql.err.ProgrammingError:
                ids = {}
            return {"composer_id": cid, "name": row["name"], "status": row["status"], "ids": ids}

    def _authority(self, name: str) -> list[dict]:
        conn = self._conn()
        with conn.cursor() as cur:
            key = composer_key(name)
            cur.execute(
                "SELECT ca.wikidata_id, ca.viaf_id, ca.canonical_name, ca.birth_date, ca.death_date "
                "FROM composer_authority ca JOIN composer_authority_names n ON n.authority_id=ca.authority_id "
                "WHERE n.normalized_name=%s", (key,))
            return [{"qid": r["wikidata_id"], "viaf": r["viaf_id"], "name": r["canonical_name"],
                     "birth": r["birth_date"], "death": r["death_date"]}
                    for r in cur.fetchall()]

    # --- fuentes de red (timeout agresivo) ---

    def _open(self, name: str) -> tuple[dict | None, bool]:
        with self._lock:
            self.wikidata_calls += 1
        rec, to = _call(lambda: composer_identifiers(name, timeout=_NET_TIMEOUT), _WALL_TIMEOUT)
        if to:
            with self._lock:
                self.timeouts += 1
            return None, True
        if rec is None:
            return None, False
        return {
            "qid": rec.wikidata, "viaf": rec.viaf, "isni": rec.isni,
            "mbid": rec.musicbrainz, "lccn": rec.lccn,
            "canonical_name": rec.canonical_name, "aliases": rec.aliases or [],
        }, False

    def _viaf(self, name: str) -> tuple[dict | None, bool]:
        with self._lock:
            self.viaf_calls += 1
        url = ("https://viaf.org/viaf/search?query="
               + urllib.parse.quote(f'local.personalNames all "{name}"')
               + "&httpAccept=application/json&maximumRecords=2&sortKeys=holdingscount")
        request = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=_NET_TIMEOUT) as resp:  # noqa: S310
                doc = json.loads(resp.read())
        except Exception:  # noqa: BLE001
            return None, True
        recs = (doc.get("searchRetrieveResponse") or {}).get("records") or []
        for rec in recs[:1]:
            rd = rec.get("record", {}).get("recordData", {})
            vid = rd.get("document", {}).get("@viafId")
            if vid:
                return {"viaf": vid, "name": name}, False
        return None, False

    # --- decisión ---

    def _decide(self, authority: list[dict], open_rec: dict | None, viaf: dict | None,
                open_to: bool, viaf_to: bool) -> tuple[str, str, str]:
        def ids_of(t: str) -> set[str]:
            out: set[str] = set()
            if open_rec:
                if t == "mbid" and open_rec.get("mbid"):
                    out.add(open_rec["mbid"])
                if t == "viaf" and open_rec.get("viaf"):
                    out.add(open_rec["viaf"])
                if t == "isni" and open_rec.get("isni"):
                    out.add(open_rec["isni"])
                if t == "qid" and open_rec.get("qid"):
                    out.add(open_rec["qid"])
            for a in authority:
                if t == "viaf" and a.get("viaf"):
                    out.add(a["viaf"])
                if t == "qid" and a.get("qid"):
                    out.add(a["qid"])
            return out

        for id_type, label in (("mbid", "resolved_by_mbid"), ("viaf", "resolved_by_viaf"),
                               ("isni", "resolved_by_isni"), ("ipi", "resolved_by_ipi")):
            vals = ids_of(id_type)
            if len(vals) == 1:
                v = next(iter(vals))
                if open_rec and open_rec.get(id_type) == v:
                    src = "open"
                elif viaf and viaf.get("viaf") == v:
                    src = "rism_viaf"
                elif any(a.get("viaf") == v for a in authority):
                    src = "authority_local"
                else:
                    src = "open"
                return label, f"{id_type}={v}", src
            if len(vals) > 1:
                return "ambiguous", f"conflicto {id_type}: {sorted(vals)}", "open"

        qids = ids_of("qid")
        if len(qids) == 1 and (open_rec and open_rec.get("viaf") or any(a.get("viaf") for a in authority)):
            return "resolved_by_qid_plus_evidence", f"qid={next(iter(qids))}", "open"

        if authority and (authority[0].get("birth") or authority[0].get("death")):
            return "resolved_by_name_dates", f"autoridad {authority[0]['qid']}", "authority_local"

        if open_to and viaf_to:
            return "unknown", "timeout en fuentes de red", "timeout"
        return "unknown", "sin identidad fiable", "unknown"

    # --- api ---

    def resolve(self, name: str, local_only: bool = False) -> tuple[str, str, dict, str, bool]:
        key = composer_key(name)
        if key in self._cache:
            st, reason, ev, src = self._cache[key]
            return st, reason, ev, src, True
        st, reason, ev, src = self._resolve_fresh(name, local_only=local_only)
        self._cache[key] = (st, reason, ev, src)
        return st, reason, ev, src, False

    def resolve_cached(self, name: str) -> tuple[str, str, dict, str]:
        key = composer_key(name)
        if key not in self._cache:
            st, reason, ev, src = self._resolve_fresh(name)
            self._cache[key] = (st, reason, ev, src)
        return self._cache[key]

    def _resolve_fresh(self, name: str, local_only: bool = False) -> tuple[str, str, dict, str]:
        if _is_anon(name):
            return "not_applicable", "anon/unknown attribution", {}, "not_applicable"

        maestro = self._maestro(name)
        if maestro:
            return "matched_existing", f"maestro composer {maestro['composer_id']}", {"maestro": maestro}, "maestro"

        authority = self._authority(name)
        if len(authority) == 1 and (authority[0].get("viaf") or authority[0].get("qid")):
            a = authority[0]
            if a.get("viaf"):
                return "resolved_by_viaf", f"viaf={a['viaf']}", {"authority": authority}, "authority_local"
            return ("resolved_by_qid_plus_evidence", f"qid={a['qid']} (autoridad local)",
                    {"authority": authority}, "authority_local")

        if local_only:
            # sin red: no resolvible con la autoridad/maestro local
            return "unknown", "sin identidad local", {"maestro": None, "authority": authority,
                                                      "open": None, "viaf": None}, "unknown"

        open_rec, open_to = self._open(name)
        viaf, viaf_to = self._viaf(name)
        evidence = {"maestro": None, "authority": authority, "open": open_rec, "viaf": viaf,
                    "open_timeout": open_to, "viaf_timeout": viaf_to}
        st, reason, src = self._decide(authority, open_rec, viaf, open_to, viaf_to)
        return st, reason, evidence, src


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--from-id", type=int, default=0)
    parser.add_argument("--test", default=f"res-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--named-only", action="store_true",
                        help="muestrear solo obras con compositor no anónimo")
    parser.add_argument("--workers", type=int, default=8,
                        help="concurrencia para resolver compositores únicos")
    parser.add_argument("--batch", type=int, default=250,
                        help="compositores únicos por lote (persistencia incremental)")
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="2027osapdb")
    parser.add_argument("--db-name", default="osap-storage")
    args = parser.parse_args()

    db = {
        "host": args.db_host, "user": args.db_user, "password": args.db_password,
        "database": args.db_name, "charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor,
    }
    resolver = IdentityResolver(db)

    conn = pymysql.connect(**db)
    t0 = time.time()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, composer FROM works WHERE id > %s ORDER BY id LIMIT %s",
                (args.from_id, args.limit * 20),
            )
            works = cur.fetchall()
        if args.named_only:
            works = [
                w for w in works
                if (w.get("composer") or "").strip() and not _is_anon(w["composer"])
            ][: args.limit]
        else:
            works = works[: args.limit]

        # reanudación: omitir obras ya persistidas para este test_id (crash-safe)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT work_id FROM composer_identity_resolution WHERE test_id=%s",
                (args.test,),
            )
            done = {int(r["work_id"]) for r in cur.fetchall()}
        if done:
            before = len(works)
            works = [w for w in works if int(w["id"]) not in done]
            print(f"[resume] omitidas {before - len(works)} obras ya en {args.test}", flush=True)
        if not works:
            print(f"todo ya procesado para {args.test}")
            return 0

        stats: Counter = Counter()
        by_source: Counter = Counter()
        works_per_composer: Counter = Counter()
        conflicts: Counter = Counter()
        new_composers: set[str] = set()
        new_aliases: set[str] = set()
        res_types: Counter = Counter()
        unique_names: dict[str, str] = {}
        works_by_key: dict[str, list] = {}
        for w in works:
            name = (w.get("composer") or "").strip()
            key = composer_key(name)
            unique_names.setdefault(key, name)
            works_by_key.setdefault(key, []).append(w)

        keys = list(unique_names)
        n_batches = max(1, -(-len(keys) // args.batch))
        for bi, start in enumerate(range(0, len(keys), args.batch), 1):
            chunk = keys[start:start + args.batch]
            # resolver el lote de compositores únicos en paralelo
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                list(ex.map(resolver.resolve, [unique_names[k] for k in chunk]))
            # persistir las obras de este lote (incremental)
            chunk_set = set(chunk)
            for k in chunk:
                for w in works_by_key[k]:
                    wid = int(w["id"])
                    name = (w.get("composer") or "").strip()
                    status, reason, evidence, source = resolver.resolve_cached(name)
                    stats[status] += 1
                    res_types[status] += 1
                    by_source[source] += 1
                    if status == "ambiguous":
                        m = re.search(r"conflicto (\w+):", reason)
                        conflicts[m.group(1) if m else "?"] += 1
                    if status.startswith("resolved"):
                        new_composers.add(name)
                        if evidence.get("open"):
                            new_aliases.update(evidence["open"].get("aliases") or [])
                        if evidence.get("authority"):
                            works_per_composer[evidence["authority"][0]["name"]] += 1
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO composer_identity_resolution (test_id, work_id, attribution, status, "
                            "decision_reason, evidence_json) VALUES (%s,%s,%s,%s,%s,%s) "
                            "ON DUPLICATE KEY UPDATE status=VALUES(status), decision_reason=VALUES(decision_reason), "
                            "evidence_json=VALUES(evidence_json)",
                            (args.test, wid, name[:1024], status, reason[:1024],
                             json.dumps(evidence, ensure_ascii=False)),
                        )
                    conn.commit()
            del chunk_set
            done = sum(res_types.values())
            print(f"[batch {bi}/{n_batches}] uniques {len(unique_names)} | obras persistidas {done} "
                  f"| resolved {sum(1 for s in res_types if s.startswith('resolved'))}", flush=True)

        elapsed = time.time() - t0
        works_resolved = sum(1 for s in res_types if s.startswith("resolved"))
        cache_hits = len(works) - len(unique_names)
        print(f"=== IDENTIDAD ESCALONADA ({len(works)} obras) test={args.test} ===")
        print(f"tiempo: {elapsed:.1f}s | {elapsed/max(len(works),1)*1000:.0f} ms/obra")
        print(f"compositores únicos / obras: {len(unique_names)} / {len(works)}")
        print(f"  cache_hits (obras reutilizando identidad cacheada): {cache_hits}")
        print("-- por capa que decide --")
        for k in ("maestro", "authority_local", "cache", "open", "rism_viaf", "timeout", "unknown", "not_applicable"):
            if by_source[k]:
                print(f"  {k:16}: {by_source[k]}")
        print("-- por decisión --")
        for k in ("not_applicable", "matched_existing", "resolved_by_mbid", "resolved_by_viaf",
                  "resolved_by_isni", "resolved_by_ipi", "resolved_by_qid_plus_evidence",
                  "resolved_by_name_dates", "ambiguous", "unknown"):
            if stats[k]:
                print(f"  {k:28}: {stats[k]}")
        print(f"  {'new_composers':28}: {len(new_composers)}")
        print(f"  {'new_aliases':28}: {len(new_aliases)}")
        print(f"  {'works_associated':28}: {works_resolved}")
        print("  composers_with_n_works (top):")
        for n_, c_ in works_per_composer.most_common(8):
            print(f"     {n_}: {c_}")
        if conflicts:
            print("  conflictos por fuente:")
            for src_, c_ in conflicts.most_common():
                print(f"     {src_}: {c_}")
        print("-- red --")
        print(f"  llamadas wikidata: {resolver.wikidata_calls} | llamadas viaf/rism: "
              f"{resolver.viaf_calls} | timeouts: {resolver.timeouts}")
        print("  MBID vía Wikidata (P434): 0 llamadas directas a MusicBrainz")
        candidatos = stats["ambiguous"] + stats["unknown"]
        print(f"  {'candidatos_de_ampliacion (ambig+unknown)':28}: {candidatos}")
        print(f"persistido en composer_identity_resolution (test={args.test})")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
