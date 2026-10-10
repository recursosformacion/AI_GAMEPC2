#!/usr/bin/env python
"""Elimina representaciones IMSLP duplicadas (misma URL en varias obras).

Una URL de IMSLP (permalink) compartida por varias obras es un **error de mapeo**: el anclaje
por título unía obras que difieren solo en el número (p. ej. «RBV 11» y «RBV 13»). Para cada
URL compartida se conserva la rep en la obra cuyo título coincide con la página de la URL y se
borran las demás, **solo si la obra conserva al menos otra rep** (nunca deja una obra sin URL).

La URL define la representación: cada URL debe vivir en una única obra. Dry-run por defecto.
No toca CPDL (ficheros de colección, se tratan aparte).

Uso (desde osap-api):
    python script/fix_imslp_rep_dupes.py            # dry-run
    python script/fix_imslp_rep_dupes.py --apply
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
    """Normaliza a alfanumérico minúsculo (conserva dígitos: el número distingue la obra)."""
    ascii_text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


def _page_core(url: str) -> str:
    """Título normalizado de la página IMSLP de la URL, sin el sufijo «(Compositor)»."""
    path = urllib.parse.urlsplit(url).path
    page = urllib.parse.unquote(path.split("/wiki/", 1)[-1]).replace("_", " ")
    page = re.sub(r"\s*\([^)]*\)\s*$", "", page).strip()
    return _norm(page)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="borra (por defecto dry-run)")
    ap.add_argument("--db-host", default="127.0.0.1")
    ap.add_argument("--db-user", default="osap2027")
    ap.add_argument("--db-password", default="2027osapdb")
    ap.add_argument("--db-api", default="osap-api")
    ap.add_argument("--limit", type=int, default=0, help="procesar solo N URLs (prueba)")
    args = ap.parse_args()

    db = pymysql.connect(host=args.db_host, user=args.db_user, password=args.db_password,
                         database=args.db_api, charset="utf8mb4",
                         cursorclass=pymysql.cursors.DictCursor)
    deletes: list[int] = []
    skipped = 0
    try:
        with db.cursor() as cur:
            # 1) URLs IMSLP compartidas por >1 obra (una sola pasada).
            cur.execute(
                "SELECT download_url FROM index_representations "
                "WHERE provider='imslp' AND download_url IS NOT NULL AND download_url<>'' "
                "GROUP BY download_url HAVING COUNT(DISTINCT work_id)>1"
            )
            dup_urls = [str(r["download_url"]) for r in cur.fetchall()]
            if args.limit:
                dup_urls = dup_urls[: args.limit]

            # 2) Todas las reps de esas URLs + obra y nº total de reps de cada obra (por lotes).
            by_url: dict[str, list[dict]] = defaultdict(list)
            for i in range(0, len(dup_urls), 500):
                chunk = dup_urls[i:i + 500]
                ph = ",".join(["%s"] * len(chunk))
                cur.execute(
                    "SELECT r.id rep_id, r.download_url u, w.id work_id, w.title, "
                    "(SELECT COUNT(*) FROM index_representations x WHERE x.work_id=w.id) nr "
                    f"FROM index_representations r JOIN index_works w ON w.id=r.work_id "
                    f"WHERE r.provider='imslp' AND r.download_url IN ({ph})",
                    chunk,
                )
                for row in cur.fetchall():
                    by_url[str(row["u"])].append(row)

        # 3) Decidir qué reps sobran.
        keeps = ambig = 0
        for url, works in by_url.items():
            core = _page_core(url)
            correct = [w for w in works if _norm(str(w["title"])) == core]
            if len(correct) != 1:
                ambig += 1
                skipped += len(works)
                continue
            keep = int(correct[0]["rep_id"])
            for w in works:
                if int(w["rep_id"]) == keep:
                    keeps += 1
                    continue
                if int(w["nr"]) <= 1:
                    skipped += 1  # no dejar la obra sin URL
                    continue
                deletes.append(int(w["rep_id"]))

        print(f"urls compartidas: {len(by_url)} | se conservan: {keeps} | a borrar: {len(deletes)} "
              f"| ambiguas: {ambig} | omitidas: {skipped}")
        if args.apply and deletes:
            with db.cursor() as cur:
                for i in range(0, len(deletes), 1000):
                    chunk = deletes[i:i + 1000]
                    ph = ",".join(["%s"] * len(chunk))
                    cur.execute(f"DELETE FROM index_representations WHERE id IN ({ph})", chunk)
            db.commit()
            print(f"borradas {len(deletes)} reps duplicadas")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
