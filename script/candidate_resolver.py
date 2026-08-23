#!/usr/bin/env python
"""Resolver de candidatos a Composer (propuestas), minimizando consultas remotas.

Toma el top N de `composer_candidate` (por impacto, agrupado por `name_key`) y decide la
resolución así, priorizando la información local:

  * >= umbral de obras (por defecto 20) -> `resolved_by_prolific` (aceptado SIN red:
    muchas obras en el corpus = evidencia real de uso; ej. Tchaikovsky, Paganini, Skinner).
  * < umbral -> por defecto resuelve SOLO con fuentes locales (maestro + composer_authority),
    cero red; con `--network` usa además VIAF/Wikidata para los que no están en local.

No crea Composer: registra `composer_candidate.resolved_status` como PROPUESTA para la
fase de validación.

Uso (en osap-api, con PYTHONPATH=osap-api):
    python script/candidate_resolver.py --limit 100 --db-name osap_storage \
        [--db-user osap] [--db-password ...] [--threshold 20] [--network]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parent))
import identity_resolver as _ir  # noqa: E402
from identity_resolver import IdentityResolver  # noqa: E402

# Resolución de candidatos: pocas llamadas, alta prioridad -> timeouts pacientes
# (el WALL de 14s del pipeline produce falsos 'unknown' bajo carga de red).
_ir._NET_TIMEOUT = 20
_ir._WALL_TIMEOUT = 45


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--label", default="real", choices=("real", "review", "all"))
    parser.add_argument("--threshold", type=int, default=20,
                        help="obras en el corpus para aceptar sin red (famoso/prolífico)")
    parser.add_argument("--network", action="store_true",
                        help="resolver además con VIAF/Wikidata los que no están en local")
    parser.add_argument("--only-status", default="",
                        help="solo candidatos con este resolved_status (p. ej. 'unknown')")
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="2027osapdb")
    parser.add_argument("--db-name", default="osap-storage")
    args = parser.parse_args()

    db = {
        "host": args.db_host, "user": args.db_user, "password": args.db_password,
        "database": args.db_name, "charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor,
    }
    conn = pymysql.connect(**db)
    try:
        where = "" if args.label == "all" else f"WHERE label='{args.label}'"
        if args.only_status:
            where = f"WHERE label='{args.label}' AND resolved_status='{args.only_status}'" \
                if args.label != "all" else f"WHERE resolved_status='{args.only_status}'"
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT attribution, name_key, cleaned_name, work_count "
                f"FROM composer_candidate {where}"
            )
            rows = cur.fetchall()

        # agrupar por identidad, sumar obras, elegir representante (el de más obras)
        groups: dict[str, dict] = {}
        for r in rows:
            key = r["name_key"]
            g = groups.setdefault(key, {"works": 0, "name": "", "raw": "", "best": 0, "count": 0})
            wc = int(r["work_count"])
            g["works"] += wc
            g["count"] += 1
            if wc > g["best"]:
                g["best"] = wc
                g["raw"] = r["attribution"]
                g["name"] = r["cleaned_name"] or r["attribution"]
        ranked = sorted(groups.items(), key=lambda kv: kv[1]["works"], reverse=True)
        if args.limit > 0:
            ranked = ranked[: args.limit]

        # resolver: prolíficos (>=threshold obras) sin red; el resto con autoridad local
        # (y con red si `--network` está activo).
        resolver = IdentityResolver(db)
        stats: Counter = Counter()
        results: list[tuple[str, str]] = []
        for key, g in ranked:
            if g["works"] >= args.threshold:
                status = "resolved_by_prolific"
                reason = f"prolific ({g['works']} obras en corpus)"
            else:
                status, reason, _ev, _src, _cached = resolver.resolve(
                    g["raw"], local_only=not args.network
                )
            stats[status] += 1
            results.append((key, status))
            print(f"  {g['works']:>5}  {status:24}  {g['raw'][:52]}", flush=True)

        with conn.cursor() as cur:
            for key, status in results:
                cur.execute(
                    "UPDATE composer_candidate SET resolved_status=%s WHERE name_key=%s",
                    (status, key))
            conn.commit()

        print(f"=== RESOLVER CANDIDATOS (top {len(ranked)}) ===")
        print(f"  obras que cubren: {sum(g['works'] for _, g in ranked):,}")
        for s, n in stats.most_common():
            print(f"  {s:26}: {n}")
        print("  persistido en composer_candidate.resolved_status")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
