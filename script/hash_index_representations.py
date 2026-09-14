# hash_index_representations.py — SHA-256 de los MusicXML del índice y dedupe por contenido.
#
# Resumen: recorre las representaciones del índice (`index_representations`), descarga cada
# fichero UNA vez (lectura de R2/CDN, con coste), guarda su `content_hash` en la tabla y
# detecta ficheros IDÉNTICOS que hoy aparecen como obras/representaciones duplicadas.
# Reanudable (`content_hash IS NULL`), con `--limit`/`--sleep` y con `--dedupe [--apply]`
# para consolidar (borra reps duplicadas conservando la de menor id, y las obras huérfanas).
#
# Uso:
#   python script/hash_index_representations.py --limit 300
#   python script/hash_index_representations.py --composer-like Myers --dedupe      # dry-run
#   python script/hash_index_representations.py --composer-like Myers --dedupe --apply

from __future__ import annotations

import argparse
import hashlib
import time

import pymysql
import requests

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _connect(args: argparse.Namespace, database: str) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=args.db_host,
        user=args.db_user,
        password=args.db_password,
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _ensure_column(conn: pymysql.connections.Connection) -> None:
    cur = conn.cursor()
    cur.execute("SHOW COLUMNS FROM index_representations LIKE 'content_hash'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE index_representations ADD COLUMN content_hash CHAR(64) NULL")
        print("  + columna content_hash creada")
    cur.execute("SHOW INDEX FROM index_representations WHERE Key_name = 'idx_rep_content_hash'")
    if not cur.fetchone():
        cur.execute("CREATE INDEX idx_rep_content_hash ON index_representations (content_hash)")
        print("  + índice idx_rep_content_hash creado")


def _pending(conn: pymysql.connections.Connection, args: argparse.Namespace) -> list[dict[str, object]]:
    where = ["r.content_hash IS NULL", "r.download_url IS NOT NULL", "r.download_url <> ''"]
    params: list[object] = []
    if args.provider:
        where.append("r.provider = %s")
        params.append(args.provider)
    if args.composer_like:
        where.append("i.composer_name LIKE %s")
        params.append(f"%{args.composer_like}%")
    if args.title_like:
        where.append("i.title LIKE %s")
        params.append(f"%{args.title_like}%")
    sql = (
        "SELECT r.id AS rep_id, r.work_id, r.download_url, i.title, i.composer_name "
        "FROM index_representations r JOIN index_works i ON i.id = r.work_id "
        f"WHERE {' AND '.join(where)} ORDER BY r.id"
    )
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    cur = conn.cursor()
    cur.execute(sql, tuple(params))
    return list(cur.fetchall())


def _hash_pending(conn: pymysql.connections.Connection, args: argparse.Namespace) -> tuple[int, int]:
    rows = _pending(conn, args)
    print(f"Pendientes de hash: {len(rows)}")
    cur = conn.cursor()
    done = 0
    errors = 0
    for index, row in enumerate(rows, start=1):
        url = str(row["download_url"])
        try:
            resp = requests.get(url, headers={"User-Agent": _BROWSER_UA, "Accept": "*/*"}, timeout=90)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            digest = hashlib.sha256(resp.content).hexdigest()
            cur.execute(
                "UPDATE index_representations SET content_hash=%s WHERE id=%s",
                (digest, row["rep_id"]),
            )
            done += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"  [error] rep {row['rep_id']}: {type(exc).__name__} {str(exc)[:120]}")
        if args.sleep:
            time.sleep(args.sleep)
        if index % 50 == 0:
            print(f"  ... {index}/{len(rows)}")
    print(f"Hasheados: {done}  errores: {errors}")
    return done, errors


def _duplicates(conn: pymysql.connections.Connection, args: argparse.Namespace) -> list[dict[str, object]]:
    cur = conn.cursor()
    cur.execute(
        "SELECT content_hash, COUNT(*) AS n FROM index_representations "
        "WHERE content_hash IS NOT NULL GROUP BY content_hash HAVING COUNT(*) > 1 "
        "ORDER BY n DESC LIMIT 500"
    )
    groups = list(cur.fetchall())
    if not groups:
        return []
    hashes = tuple(str(g["content_hash"]) for g in groups)
    placeholders = ", ".join(["%s"] * len(hashes))
    cur.execute(
        "SELECT r.id AS rep_id, r.work_id, r.content_hash, i.title, i.composer_name "
        f"FROM index_representations r JOIN index_works i ON i.id = r.work_id "
        f"WHERE r.content_hash IN ({placeholders}) ORDER BY r.content_hash, r.id",
        hashes,
    )
    return list(cur.fetchall())


def _dedupe(conn: pymysql.connections.Connection, args: argparse.Namespace, rows: list[dict[str, object]]) -> None:
    by_hash: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_hash.setdefault(str(row["content_hash"]), []).append(row)
    dup_reps: list[int] = []
    for digest, group in by_hash.items():
        keep = min(int(r["rep_id"]) for r in group)
        for row in group:
            if int(row["rep_id"]) != keep:
                dup_reps.append(int(row["rep_id"]))
        work_ids = sorted({int(r["work_id"]) for r in group})
        print(f"  hash {digest[:12]}… obras={work_ids} reps={[r['rep_id'] for r in group]} conserva={keep}")
    if not dup_reps:
        return
    if not args.apply:
        print(f"DRY-RUN: se borrarían {len(dup_reps)} representaciones duplicadas (usa --apply).")
        return
    cur = conn.cursor()
    placeholders = ", ".join(["%s"] * len(dup_reps))
    cur.execute(f"DELETE FROM index_representations WHERE id IN ({placeholders})", tuple(dup_reps))
    cur.execute(
        "DELETE w FROM index_works w LEFT JOIN index_representations r ON r.work_id = w.id "
        "WHERE r.id IS NULL"
    )
    print(f"Aplicado: {len(dup_reps)} reps duplicadas borradas y obras huérfanas limpiadas.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="máximo de reps a hashear (0 = todas)")
    parser.add_argument("--sleep", type=float, default=0.0, help="pausa entre descargas (s)")
    parser.add_argument("--provider", default="omr")
    parser.add_argument("--composer-like", default=None)
    parser.add_argument("--title-like", default=None)
    parser.add_argument("--dedupe", action="store_true", help="informa/aplica la consolidación por hash")
    parser.add_argument("--apply", action="store_true", help="con --dedupe, hace los borrados")
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="2027osapdb")
    parser.add_argument("--db-api", default="osap-api")
    args = parser.parse_args()

    conn = _connect(args, args.db_api)
    try:
        _ensure_column(conn)
        _hash_pending(conn, args)
        rows = _duplicates(conn, args)
        print(f"\nGrupos de ficheros IDÉNTICOS (mismo sha256): {len({r['content_hash'] for r in rows})}")
        for row in rows:
            print(f"  {str(row['content_hash'])[:12]}… work={row['work_id']} {row['title']} | {row['composer_name']}")
        if args.dedupe:
            _dedupe(conn, args, rows)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
