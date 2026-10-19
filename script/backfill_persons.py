"""Backfill de persons: años desde la biografía, nombre partido y nacionalidad única.

Lee `osap_storage.persons` (vía ssh + sudo mysql, JSON por línea) y genera un SQL con
`UPDATE` que solo rellena campos vacíos (COALESCE). No borra ni sobrescribe datos.

- Años: de `persons_biography_summary` con rango "(1685–1750)".
- given/family/sort: del nombre completo (respeta partículas: van, von, de, da…).
- Nacionalidad: si `persons_nationality` está vacía, copia `persons_biography_nationality`.
Uso: `python script/backfill_persons.py --out updates.sql`
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

YEAR_RANGE = re.compile(r"\(?\b(\d{3,4})\s*[-\u2013\u2014]\s*(\d{3,4})\b\)?")
PARTICLES = {"van", "von", "de", "da", "di", "del", "der", "la", "le", "dos", "das", "do"}

QUERY = (
    "SELECT JSON_OBJECT("
    "'id',persons_id,'name',persons_name,'by',persons_birth_year,'dy',persons_death_year,"
    "'gn',persons_givenname,'fn',persons_familyname,'sn',persons_sortname,"
    "'nat',persons_nationality,'bnat',persons_biography_nationality,"
    "'sum',persons_biography_summary,'type',persons_type"
    ") FROM persons"
)


def split_name(name: str) -> tuple[str | None, str | None]:
    cleaned = " ".join(name.split())
    if "," in cleaned:
        family, given = (p.strip() for p in cleaned.split(",", 1))
        return (given or None), (family or None)
    parts = cleaned.split()
    if len(parts) == 1:
        return None, parts[0]
    i = len(parts) - 1
    while i - 1 > 0 and parts[i - 1].lower() in PARTICLES:
        i -= 1
    return (" ".join(parts[:i]) or None), " ".join(parts[i:])


def hex_literal(value: str) -> str:
    return f"CONVERT(UNHEX('{value.encode('utf-8').hex()}') USING utf8mb4)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="updates.sql")
    ap.add_argument("--remote", default="RemoteIA")
    args = ap.parse_args()

    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", args.remote,
         f'sudo mysql -N -B -r osap_storage -e "{QUERY}"'],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    statements: list[str] = []
    stats = {"years": 0, "names": 0, "nat": 0, "rows": 0}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        sets: list[str] = []
        summary = str(row.get("sum") or "")
        m = YEAR_RANGE.search(summary)
        if m and not row.get("by") and not row.get("dy"):
            sets.append(f"persons_birth_year = COALESCE(NULLIF(persons_birth_year,''), '{m.group(1)}')")
            sets.append(f"persons_death_year = COALESCE(NULLIF(persons_death_year,''), '{m.group(2)}')")
            stats["years"] += 1
        if not row.get("nat") and row.get("bnat"):
            sets.append(
                f"persons_nationality = COALESCE(NULLIF(persons_nationality,''), {hex_literal(str(row['bnat']))})"
            )
            stats["nat"] += 1
        name = str(row.get("name") or "").strip()
        if (
            name
            and str(row.get("type") or "person") == "person"
            and not row.get("gn")
            and not row.get("fn")
            and not row.get("sn")
        ):
            given, family = split_name(name)
            if given and family:
                sets.append(f"persons_givenname = {hex_literal(given)}")
                sets.append(f"persons_familyname = {hex_literal(family)}")
                sets.append(f"persons_sortname = {hex_literal(f'{family}, {given}')}")
                stats["names"] += 1
        if sets:
            statements.append(
                f"UPDATE persons SET {', '.join(sets)} "
                f"WHERE persons_id = '{row['id']}';"
            )
            stats["rows"] += 1
    Path(args.out).write_text("\n".join(statements) + "\n", encoding="utf-8")
    print(stats, "->", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
