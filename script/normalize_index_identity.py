#!/usr/bin/env python
"""Normalización de identidad del índice: consolida `index_works` duplicados.

Criterio (aprobado):
1. **Catálogo completo + compositor + título**: mismo catálogo identificador único
   (K.618, BWV.232…), mismo compositor y título compatible (subconjunto de palabras
   significativas), con los **marcadores de movimiento iguales** (No.7, II, Variation 3)
   para no unir números distintos de un ciclo (D.911 No.7 ≠ No.8).
2. **Mismo compositor y mismo título**, con o sin catálogo → se unen (Regla A).
3. **Mismo título y mismo catálogo**, uno sin compositor y otro con compositor → se unen
   en la obra con compositor (Regla B).

NO toca el agrupador en runtime ni sus criterios: es una tarea de datos del índice.

Uso (desde osap-api):
    python script/normalize_index_identity.py            # dry-run (no modifica)
    python script/normalize_index_identity.py --apply    # aplica la consolidación
"""

from __future__ import annotations

import argparse
import contextlib
import re
import sys
from pathlib import Path

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))
import index_works as iw  # noqa: E402


def _markers(row: dict[str, object]) -> set[str]:
    """Marcadores ya precalculados en la fila (No.7, II, Variation 3…)."""
    return row["markers"]  # type: ignore[return-value]


def _compute_markers(title: str, catalogue: str) -> set[str]:
    """Números/romanos del título que no forman parte del catálogo (movimientos)."""
    tokens = iw.title_key(title).split()
    cat_tokens = set(iw._canonical_catalogue_identity(catalogue).split())
    return {
        t
        for t in tokens
        if (t.isdigit() or re.fullmatch(r"[ivxlcdm]+", t)) and t not in cat_tokens
    }


def _same_work(a: dict[str, object], b: dict[str, object]) -> bool:
    ca, cb = str(a["cat"]), str(b["cat"])
    ua = bool(ca) and iw._is_unique_catalogue(ca)
    ub = bool(cb) and iw._is_unique_catalogue(cb)
    if ua and ub and ca != cb:
        return False
    sa, sb = a["sig"], b["sig"]
    same_title = a["tkey"] == b["tkey"]
    compatible_title = same_title or sa <= sb or sb <= sa  # type: ignore[operator]
    if (ua or ub) and not (ua and ub):
        # Anclaje: un lado identificado por catálogo, el otro sin él.
        return _markers(a) == _markers(b) and compatible_title
    if ua and ub:
        return _markers(a) == _markers(b) and compatible_title
    # Regla A: sin catálogo único en ninguno -> mismo título exacto.
    return same_title


def main() -> int:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="aplica la consolidación (por defecto dry-run)")
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="2027osapdb")
    parser.add_argument("--db-api", default="osap-api")
    args = parser.parse_args()

    conn = pymysql.connect(
        host=args.db_host, user=args.db_user, password=args.db_password,
        database=args.db_api, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )
    groups_done = 0
    absorbed = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, composer_name, composer_id, catalogue FROM index_works"
            )
            raw = list(cur.fetchall())

        rows: list[dict[str, object]] = []
        for row in raw:
            composer = iw.composer_key(str(row["composer_name"] or "")) or str(
                row["composer_id"] or ""
            ).strip()
            rows.append(
                {
                    "id": int(row["id"]),
                    "title": str(row["title"] or ""),
                    "catalogue": str(row["catalogue"] or ""),
                    "cat": iw._canonical_catalogue_identity(str(row["catalogue"] or "")),
                    "composer": composer,
                    "sig": iw._significant_tokens(str(row["title"] or "")),
                    "tkey": iw.title_key(str(row["title"] or "")),
                    "markers": _compute_markers(str(row["title"] or ""), str(row["catalogue"] or "")),
                }
            )

        # Grupos por compositor con índice invertido token -> grupos (rendimiento).
        clusters: dict[str, list[dict[str, object]]] = {}
        inverted: dict[str, dict[str, set[int]]] = {}
        no_composer: list[dict[str, object]] = []
        for row in rows:
            composer = str(row["composer"])
            if not composer:
                no_composer.append(row)
                continue
            sig = row["sig"]
            candidates: set[int] = set()
            for token in sig:  # type: ignore[union-attr]
                candidates |= inverted.get(composer, {}).get(token, set())
            placed = False
            for idx in candidates:
                entry = clusters[composer][idx]
                anchor = entry["anchor"]
                # Prefiltro: al menos 2 palabras significativas en común con el ancla.
                if len(sig & anchor["sig"]) < 2:  # type: ignore[operator]
                    continue
                if _same_work(anchor, row):  # type: ignore[arg-type]
                    entry["rows"].append(row)  # type: ignore[union-attr]
                    placed = True
                    break
            if not placed:
                entries = clusters.setdefault(composer, [])
                entries.append({"anchor": row, "rows": [row]})
                new_idx = len(entries) - 1
                for token in sig:  # type: ignore[union-attr]
                    inverted.setdefault(composer, {}).setdefault(token, set()).add(new_idx)

        # Pasada final: los grupos sin catálogo se absorben en el grupo identificado
        # (mismo compositor y título contenido), con índice invertido para no ser O(C²).
        for entries in clusters.values():
            identified: list[tuple[dict[str, object], dict[str, object]]] = []
            for entry in entries:
                member = next(
                    (m for m in entry["rows"] if iw._is_unique_catalogue(str(m["cat"]))),  # type: ignore[union-attr]
                    None,
                )
                if member is not None:
                    identified.append((entry, member))
            if not identified:
                continue
            identified_entries = {id(entry) for entry, _m in identified}
            inv_ident: dict[str, list[tuple[dict[str, object], dict[str, object]]]] = {}
            for pair in identified:
                for token in pair[1]["sig"]:  # type: ignore[union-attr]
                    inv_ident.setdefault(token, []).append(pair)
            others = [e for e in entries if id(e) not in identified_entries]
            merged_into: set[int] = set()
            for other in others:
                candidates: set[int] = set()
                for token in other["anchor"]["sig"]:  # type: ignore[union-attr]
                    for pair in inv_ident.get(token, []):
                        candidates.add(id(pair[0]))
                for entry, cat_member in identified:
                    if id(entry) in candidates and _same_work(cat_member, other["anchor"]):  # type: ignore[arg-type]
                        entry["rows"].extend(other["rows"])  # type: ignore[union-attr]
                        merged_into.add(id(other))
                        break
            for other in others:
                if id(other) in merged_into:
                    entries.remove(other)

        # Regla B: sin compositor, mismo título y catálogo que una obra con compositor.
        attached_no_composer = 0
        by_cat: dict[str, list[tuple[str, int]]] = {}
        for composer, entries in clusters.items():
            for idx, entry in enumerate(entries):
                cat = str(entry["anchor"]["cat"])
                if cat:
                    by_cat.setdefault(cat, []).append((composer, idx))
        for row in no_composer:
            cat = str(row["cat"])
            if not (cat and iw._is_unique_catalogue(cat)):
                continue
            for composer, idx in by_cat.get(cat, []):
                entry = clusters[composer][idx]
                if entry["anchor"]["tkey"] == row["tkey"]:
                    entry["rows"].append(row)  # type: ignore[union-attr]
                    attached_no_composer += 1
                    break

        candidates = [
            entry["rows"]
            for entries in clusters.values()
            for entry in entries
            if len(entry["rows"]) > 1  # type: ignore[arg-type]
        ]
        candidate_ids = [int(m["id"]) for members in candidates for m in members]
        counts: dict[int, int] = {}
        if candidate_ids:
            with conn.cursor() as cur:
                placeholders = ", ".join(["%s"] * len(candidate_ids))
                cur.execute(
                    f"SELECT work_id, COUNT(*) AS n FROM index_representations "
                    f"WHERE work_id IN ({placeholders}) GROUP BY work_id",
                    candidate_ids,
                )
                counts = {int(r["work_id"]): int(r["n"]) for r in cur.fetchall()}
        print(
            f"obras: {len(rows)} | grupos candidatos: {len(candidates)} | "
            f"sin compositor ancladas: {attached_no_composer}"
        )
        cur = conn.cursor()
        for members in sorted(candidates, key=lambda c: -len(c)):
            survivor = max(
                members,
                key=lambda m: (
                    bool(str(m["composer"])),
                    bool(str(m["catalogue"]).strip()),
                    counts.get(int(m["id"]), 0),
                ),
            )
            mergeable = [m for m in members if m["id"] != survivor["id"]]
            if not mergeable:
                continue
            total = sum(counts.get(int(m["id"]), 0) for m in [survivor, *mergeable])
            label = str(survivor["cat"]) or "(sin catálogo)"
            print(
                f"  cat={label} survivor={survivor['id']} '{str(survivor['title'])[:60]}' "
                f"+ {len(mergeable)} obras -> {total} reps"
            )
            groups_done += 1
            absorbed += len(mergeable)
            if not args.apply:
                continue
            best = max([survivor, *mergeable], key=lambda r: counts.get(int(r["id"]), 0))
            cur.execute(
                "UPDATE index_works SET title=%s, composer_name=%s, catalogue=%s WHERE id=%s",
                (
                    str(best["title"])[:1024],
                    str(best["composer"]) or None,
                    str(best["catalogue"]) or None,
                    survivor["id"],
                ),
            )
            for member in mergeable:
                cur.execute(
                    "INSERT INTO index_representations "
                    "(work_id, provider, format, download_url, title_provider, available, quality) "
                    "SELECT %s, provider, format, download_url, title_provider, available, quality "
                    "FROM index_representations WHERE work_id=%s "
                    "ON DUPLICATE KEY UPDATE download_url=VALUES(download_url), "
                    "available=VALUES(available), quality=VALUES(quality)",
                    (survivor["id"], member["id"]),
                )
                cur.execute("DELETE FROM index_representations WHERE work_id=%s", (member["id"],))
                cur.execute("DELETE FROM index_works WHERE id=%s", (member["id"],))
            cur.execute(
                "UPDATE index_works w SET w.source_count = ("
                "SELECT COUNT(DISTINCT provider) FROM index_representations r WHERE r.work_id = w.id) "
                "WHERE w.id=%s",
                (survivor["id"],),
            )
        if args.apply:
            conn.commit()
            print(f"aplicado: {groups_done} grupos consolidados, {absorbed} obras absorbidas")
        else:
            print(f"dry-run: se consolidarían {groups_done} grupos ({absorbed} obras absorbidas)")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
