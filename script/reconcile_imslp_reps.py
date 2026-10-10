#!/usr/bin/env python
"""Reconcilia representaciones IMSLP mal asignadas por número/Op.

El anclaje por título (que descartaba dígitos) metió reps de una página IMSLP en la obra de
otro número/Op. (p. ej. la rep de «…, Op.122» dentro de la obra «…, Op.97»). Este pase compara
los **números** de la página de la URL con los del título de la obra; si difieren, la rep está
mal asignada:

  - si existe **una** obra candidata (mismo compositor + mismos números + core de título
    coincidente), la rep se **reasigna** a esa obra (o se borra si esa obra ya tiene la misma
    rep);
  - si no hay candidata clara, la rep se **borra** (la URL no pertenece a esa obra).

Nunca deja una obra sin ninguna URL. Dry-run por defecto. No toca CPDL.

Uso (desde osap-api):
    python script/reconcile_imslp_reps.py            # dry-run
    python script/reconcile_imslp_reps.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
import urllib.parse
from collections import defaultdict
from pathlib import Path

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _norm(text: str | None) -> str:
    ascii_text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


def _core(text: str | None) -> str:
    """Título sin sufijo final «(...)», normalizado."""
    return _norm(re.sub(r"\s*\([^)]*\)\s*$", "", str(text or "")).strip())


def _numbers(text: str | None) -> frozenset[str]:
    """Números del texto, extracción directa (title_key descartaría los de catálogo)."""
    return frozenset(re.findall(r"\d+", str(text or "")))


def _page_title(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    return urllib.parse.unquote(path.split("/wiki/", 1)[-1]).replace("_", " ")


def _composer_key(person_id: object, composer_name: object) -> str:
    return str(person_id) if person_id else _norm(str(composer_name or ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db-host", default="127.0.0.1")
    ap.add_argument("--db-user", default="osap2027")
    ap.add_argument("--db-password", default="2027osapdb")
    ap.add_argument("--db-api", default="osap-api")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    db = pymysql.connect(host=args.db_host, user=args.db_user, password=args.db_password,
                         database=args.db_api, charset="utf8mb4",
                         cursorclass=pymysql.cursors.DictCursor)
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, title, composer_name, person_id FROM index_works")
            works = cur.fetchall()
            # índice de obras por (compositor, números) → [(id, core)]
            by_key: dict[tuple[str, frozenset[str]], list[tuple[int, str]]] = defaultdict(list)
            core_by_work: dict[int, str] = {}
            for w in works:
                core = _core(str(w["title"]))
                core_by_work[int(w["id"])] = core
                by_key[(_composer_key(w["person_id"], w["composer_name"]), _numbers(str(w["title"])))].append(
                    (int(w["id"]), core)
                )
            # reps IMSLP + nº total de reps de la obra
            cur.execute(
                "SELECT r.id, r.work_id, r.download_url u, r.title_provider tp, r.format fmt, "
                "r.source_rep_id sr, r.resource_id rid, w.title, "
                "w.composer_name, w.person_id, "
                "(SELECT COUNT(*) FROM index_representations x WHERE x.work_id=w.id) nr "
                "FROM index_representations r JOIN index_works w ON w.id=r.work_id "
                "WHERE r.provider='imslp' AND r.download_url IS NOT NULL AND r.download_url<>''"
            )
            reps = cur.fetchall()
            if args.limit:
                reps = reps[: args.limit]

            reassign: list[tuple[int, int, str, str, str, int]] = []  # (rep, target, page, fmt, sr, rid)
            delete: list[tuple[int, str, str]] = []  # (rep_id, page_title, work_title)
            ok = ambiguous = 0
            for r in reps:
                page = _page_title(str(r["u"]))
                n_page = _numbers(page)
                n_title = _numbers(str(r["title"]))
                if not n_page or not n_title or n_page == n_title:
                    ok += 1
                    continue
                ckey = _composer_key(r["person_id"], r["composer_name"])
                cands = by_key.get((ckey, n_page), [])
                cpage = _core(page)
                exact = [w for w in cands if w[1] == cpage]
                target = exact[0] if len(exact) == 1 else (cands[0] if len(cands) == 1 else None)
                if target is None:
                    ambiguous += 1
                    if int(r["nr"]) > 1:
                        delete.append((int(r["id"]), page, str(r["title"])))
                    continue
                if target[0] == int(r["work_id"]):
                    ok += 1
                    continue
                if str(r["tp"]) == page:  # la obra destino ya tendría esta misma rep
                    delete.append((int(r["id"]), page, str(r["title"])))
                else:
                    reassign.append((int(r["id"]), target[0], page, str(r["fmt"]),
                                     str(r["sr"] or ""), int(r["rid"] or 0)))

            print(f"reps IMSLP: {len(reps)} | ok: {ok} | reasignar: {len(reassign)} "
                  f"| borrar: {len(delete)} | ambiguas: {ambiguous}")
            for rep_id, tw, page, _f, _s, _r in reassign[:6]:
                print(f"  MOVE rep {rep_id} -> work {tw} ({page[:45]})")
            for rep_id, page, title in delete[:10]:
                print(f"  DEL  rep {rep_id} | url «{page[:45]}» != titulo «{title[:40]}»")
            if args.apply:
                moved = 0
                with db.cursor() as cur:
                    for rep_id, tw, page, fmt, sr, rid in reassign:
                        cur.execute(
                            "SELECT 1 FROM index_representations WHERE work_id=%s AND provider='imslp' "
                            "AND source_rep_id=%s AND resource_id=%s AND format=%s "
                            "AND title_provider=%s LIMIT 1",
                            (tw, sr, rid, fmt, page[:1024]))
                        if cur.fetchone():  # ya existe la misma rep en el destino → borrar
                            delete.append((rep_id, page, ""))
                            continue
                        cur.execute(
                            "UPDATE index_representations SET work_id=%s, title_provider=%s "
                            "WHERE id=%s", (tw, page[:1024], rep_id))
                        moved += 1
                    ids = [d[0] for d in delete]
                    for i in range(0, len(ids), 1000):
                        chunk = ids[i:i + 1000]
                        ph = ",".join(["%s"] * len(chunk))
                        cur.execute(f"DELETE FROM index_representations WHERE id IN ({ph})", chunk)
                db.commit()
                print(f"aplicado: {moved} reasignadas, {len(delete)} borradas")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
