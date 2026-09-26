#!/usr/bin/env python
"""Resuelve el compositor de `index_works` a la persona canónica del Maestro.

Regla (autoridad = `persons`): el índice guarda `person_id` (clave de `persons`) y
`composer_name` **copiado de `persons.persons_name`** (canónico), no el texto del proveedor.

- Construye un mapa `clave_de_nombre -> (persons_id, persons_name)` a partir de `persons`
  (activas) y `persons_aliases`, quedándose con la persona de más obras (rol 1).
- La clave unifica orden (`Mozart, Wolfgang Amadeus` == `Wolfgang Amadeus Mozart`) y
  colapsa iniciales vía `MetadataNormalizer.comparison_composer`.
- Para cada fila de `index_works`: si tiene `person_id`, la remapea a la persona canónica de
  su clave; si no, resuelve por `composer_name`.

Dry-run por defecto. Uso (desde osap-api):
    python script/resolve_index_composers.py
    python script/resolve_index_composers.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.osap.application.metadata_normalizer import MetadataNormalizer  # noqa: E402


def name_key(name: str | None) -> frozenset[str]:
    cleaned = MetadataNormalizer.comparison_composer(str(name or "").replace(",", " "))
    return frozenset(t for t in cleaned.split() if t)


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db-host", default="127.0.0.1")
    ap.add_argument("--db-user", default="osap2027")
    ap.add_argument("--db-password", default="2027osapdb")
    args = ap.parse_args()

    st = pymysql.connect(host=args.db_host, user=args.db_user, password=args.db_password,
                         database="osap-storage", charset="utf8mb4",
                         cursorclass=pymysql.cursors.DictCursor)
    with st, st.cursor() as cur:
        cur.execute("SELECT persons_id, persons_name FROM persons WHERE persons_status='active'")
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

    best: dict[frozenset[str], tuple[str, str]] = {}

    def offer(key: frozenset[str], pid: str, name: str) -> None:
        if not key:
            return
        cur_best = best.get(key)
        if cur_best is None or counts.get(pid, 0) > counts.get(cur_best[0], 0):
            best[key] = (pid, name)

    by_id: dict[str, str] = {}
    for p in persons:
        pid, name = str(p["persons_id"]), str(p["persons_name"])
        by_id[pid] = name
        offer(name_key(name), pid, name)
    for a in aliases:
        pid = str(a["person_id"])
        offer(name_key(a["a"]), pid, by_id.get(pid, ""))

    id_to_canon = {}
    for p in persons:
        pid, name = str(p["persons_id"]), str(p["persons_name"])
        c = best.get(name_key(name))
        id_to_canon[pid] = c

    api = pymysql.connect(host=args.db_host, user=args.db_user, password=args.db_password,
                          database="osap-api", charset="utf8mb4",
                          cursorclass=pymysql.cursors.DictCursor)
    changed = resolved = unresolved = 0
    samples: list[tuple] = []
    with api.cursor() as cur:
        cur.execute("SELECT id, title, composer_name, person_id FROM index_works")
        rows = cur.fetchall()
        updates: list[tuple[str | None, str | None, int]] = []
        for r in rows:
            pid = str(r["person_id"]) if r["person_id"] else ""
            canon = id_to_canon.get(pid) if pid else None
            if canon is None:
                canon = best.get(name_key(r["composer_name"]))
            if canon is None:
                if r["composer_name"]:
                    unresolved += 1
                continue
            cid, cname = canon
            if str(r["person_id"] or "") != cid or str(r["composer_name"] or "") != cname:
                updates.append((cid, cname, int(r["id"])))
                changed += 1
                if "mozart" in (cname or "").lower() and len(samples) < 6:
                    samples.append((r["id"], r["composer_name"], r["person_id"], cname, cid))
            else:
                resolved += 1
    print(f"filas: {len(rows)} | sin cambio: {resolved} | a actualizar: {changed} | sin resolver: {unresolved}")
    for s in samples:
        print("   ", s)
    if args.apply and updates:
        with api.cursor() as cur:
            cur.executemany(
                "UPDATE index_works SET person_id=%s, composer_name=%s WHERE id=%s", updates
            )
        api.commit()
        print(f"aplicado: {len(updates)} filas")
    elif not args.apply:
        print("dry-run: no se ha modificado nada")
    api.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
