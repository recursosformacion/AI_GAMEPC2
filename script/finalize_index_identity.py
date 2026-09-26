#!/usr/bin/env python
"""Cierre de identidad del índice: resuelve el compositor a `persons` Y fusiona en un paso.

Por qué en un solo paso: si primero se reescribe `person_id` al canónico, dos filas que
representan la misma obra chocan con la clave única `(title_key, person_id)`. Aquí se agrupa
por `(title_key, persona canónica)`, se fusionan las representaciones en la superviviente y
solo entonces se fija `person_id` + `composer_name` canónico.

Autoridad = `persons` (osap-storage). El índice guarda `person_id` (clave) y
`composer_name` como copia canónica de `persons.persons_name`.

Dry-run por defecto.
    python script/finalize_index_identity.py
    python script/finalize_index_identity.py --apply
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


def build_canonical_map(host: str, user: str, password: str) -> tuple[dict, dict]:
    """(clave_nombre -> (id,nombre)) y (person_id -> canónico)."""
    st = pymysql.connect(host=host, user=user, password=password, database="osap-storage",
                         charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    with st, st.cursor() as cur:
        cur.execute("SELECT persons_id, persons_name FROM persons WHERE persons_status='active'")
        persons = cur.fetchall()
        cur.execute(
            "SELECT works_person_roles_person_id AS pid, COUNT(*) AS n "
            "FROM works_person_roles WHERE works_person_roles_role_id = 1 GROUP BY pid"
        )
        counts = {str(r["pid"]): int(r["n"]) for r in cur.fetchall()}
        cur.execute("SELECT person_id, person_aliases_normalized_alias AS a FROM persons_aliases")
        aliases = cur.fetchall()

    best_by_key: dict[frozenset, tuple[str, str]] = {}
    by_id = {str(p["persons_id"]): str(p["persons_name"]) for p in persons}
    person_key = {pid: name_key(name) for pid, name in by_id.items()}

    # Persona dominante por clase de identidad (mismo name_key).
    dominant: dict[frozenset, str] = {}
    for pid in by_id:
        key = person_key[pid]
        if not key:
            continue
        cur = dominant.get(key)
        if cur is None or counts.get(pid, 0) > counts.get(cur, 0):
            dominant[key] = pid

    # Consistencia: TODO nombre/alias de una clase apunta a la dominante de su clase.
    id_to_canon: dict[str, tuple[str, str]] = {}
    for pid in by_id:
        dom = dominant.get(person_key[pid], pid)
        id_to_canon[pid] = (dom, by_id.get(dom, by_id[pid]))
    for pid in by_id:
        best_by_key[person_key[pid]] = id_to_canon[pid]
    for a in aliases:
        pid = str(a["person_id"])
        if pid in id_to_canon:
            best_by_key.setdefault(name_key(a["a"]), id_to_canon[pid])
    return best_by_key, id_to_canon


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db-host", default="127.0.0.1")
    ap.add_argument("--db-user", default="osap2027")
    ap.add_argument("--db-password", default="2027osapdb")
    args = ap.parse_args()

    best, id_to_canon = build_canonical_map(args.db_host, args.db_user, args.db_password)
    api = pymysql.connect(host=args.db_host, user=args.db_user, password=args.db_password,
                          database="osap-api", charset="utf8mb4",
                          cursorclass=pymysql.cursors.DictCursor)
    with api.cursor() as cur:
        cur.execute(
            "SELECT w.id, w.title, w.title_key, w.composer_name, w.person_id, "
            "(SELECT COUNT(*) FROM index_representations r WHERE r.work_id = w.id) AS reps "
            "FROM index_works w"
        )
        rows = cur.fetchall()

    groups: dict[tuple[str, str], list[dict]] = {}
    unresolved = 0
    for r in rows:
        pid = str(r["person_id"]) if r["person_id"] else ""
        canon = id_to_canon.get(pid) if pid else None
        if canon is None:
            canon = best.get(name_key(r["composer_name"]))
        if canon is None:
            if r["composer_name"]:
                unresolved += 1
            continue
        cid = canon[0]
        # Clave de agrupación = clave única REAL del índice: `title_key(191)` + persona.
        groups.setdefault((str(r["title_key"])[:191], cid), []).append(
            {**r, "_cid": cid, "_cname": canon[1]}
        )

    merge_groups = {k: v for k, v in groups.items() if len(v) > 1}
    rename_only = [
        v[0]
        for v in groups.values()
        if len(v) == 1
        and (str(v[0]["person_id"] or "") != v[0]["_cid"] or str(v[0]["composer_name"] or "") != v[0]["_cname"])
    ]
    absorbed = sum(len(v) - 1 for v in merge_groups.values())
    print(
        f"filas={len(rows)} | grupos únicos={len(groups)} | a fusionar={len(merge_groups)} "
        f"({absorbed} absorbidas) | solo renombrar={len(rename_only)} | sin resolver={unresolved}"
    )
    for (tkey, cid), members in list(merge_groups.items())[:8]:
        print(f"   {tkey[:40]!r} {cid[:8]} -> survivor {members[0]['id']} + {len(members)-1}")

    if not args.apply:
        print("dry-run: sin cambios")
        return 0

    with api.cursor() as cur:
        for members in merge_groups.values():
            survivor = max(members, key=lambda m: (int(m["reps"]), m["id"]))
            for m in members:
                if m["id"] == survivor["id"]:
                    continue
                cur.execute(
                    "INSERT INTO index_representations "
                    "(work_id, provider, source_rep_id, resource_id, format, download_url, "
                    "title_provider, available, quality) "
                    "SELECT %s, provider, source_rep_id, resource_id, format, download_url, "
                    "title_provider, available, quality "
                    "FROM index_representations WHERE work_id=%s "
                    "ON DUPLICATE KEY UPDATE download_url=VALUES(download_url), "
                    "available=VALUES(available), quality=VALUES(quality)",
                    (survivor["id"], m["id"]),
                )
                cur.execute("DELETE FROM index_representations WHERE work_id=%s", (m["id"],))
                cur.execute("DELETE FROM index_work_voicings WHERE work_id=%s", (m["id"],))
                cur.execute("DELETE FROM index_works WHERE id=%s", (m["id"],))
            cur.execute(
                "UPDATE index_works SET person_id=%s, composer_name=%s WHERE id=%s",
                (survivor["_cid"], survivor["_cname"], survivor["id"]),
            )
            cur.execute(
                "UPDATE index_works w SET w.source_count = (SELECT COUNT(DISTINCT provider) "
                "FROM index_representations r WHERE r.work_id = w.id) WHERE w.id=%s",
                (survivor["id"],),
            )
        for r in rename_only:
            cur.execute(
                "UPDATE index_works SET person_id=%s, composer_name=%s WHERE id=%s",
                (r["_cid"], r["_cname"], r["id"]),
            )
    api.commit()
    print(f"aplicado: {len(merge_groups)} grupos fusionados, {len(rename_only)} renombrados")
    api.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
