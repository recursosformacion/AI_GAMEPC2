# audit_omr_titles.py — Auditoría de títulos/compositor de los MusicXML de OMR.
#
# Resumen: abre cada fichero MXL de OMR (lectura de R2/CDN, con coste), extrae el título y
# el compositor INTERNOS del MusicXML y los guarda en `index_representations.xml_title` /
# `xml_composer`. Compara con lo anunciado en `index_works` y lista los desajustes; con
# `--apply` corrige el título (y el compositor si el fichero lo trae y el índice no) para
# que lo anunciado corresponda a la partitura. Reanudable (`xml_title IS NULL`).
#
# Uso:
#   python script/audit_omr_titles.py --limit 50              # informa (no escribe títulos)
#   python script/audit_omr_titles.py --provider omr --apply   # corrige index_works
#
# Ojo: `--apply` cambia el título anunciado. El título anterior se conserva en
# `index_representations.xml_title` (evidencia) y en el log del script.

from __future__ import annotations

import argparse
import io
import re
import time
import unicodedata
import zipfile

import pymysql
import requests

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())


def _tokens(text: str, *, min_len: int = 3) -> set[str]:
    return {t for t in _norm(text).split() if len(t) >= min_len}


def _connect(args: argparse.Namespace) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=args.db_host,
        user=args.db_user,
        password=args.db_password,
        database=args.db_api,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _ensure_columns(conn: pymysql.connections.Connection) -> None:
    cur = conn.cursor()
    cur.execute("SHOW COLUMNS FROM index_representations")
    columns = {row["Field"] for row in cur.fetchall()}
    for name, ddl in (
        ("xml_title", "VARCHAR(512) NULL"),
        ("xml_composer", "VARCHAR(255) NULL"),
    ):
        if name not in columns:
            cur.execute(f"ALTER TABLE index_representations ADD COLUMN {name} {ddl}")
            print(f"  + columna {name} creada")


def _xml_metadata(data: bytes) -> tuple[str, str]:
    """(título, compositor) internos del MusicXML (MXL comprimido o XML plano)."""
    xml = ""
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = [
                n for n in zf.namelist() if n.lower().endswith(".xml") and "META-INF" not in n
            ]
            if names:
                xml = zf.read(names[0]).decode("utf-8", "replace")
    elif data[:5] in (b"<?xml", b"<scor", b"<?XML"):
        xml = data.decode("utf-8", "replace")
    if not xml:
        return "", ""
    title_match = re.search(r"<movement-title>(.*?)</movement-title>", xml, re.S) or re.search(
        r"<work-title>(.*?)</work-title>", xml, re.S
    )
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
    creators = re.findall(r"<creator[^>]*>(.*?)</creator>", xml, re.S)
    composer = ""
    for creator in creators:
        text = re.sub(r"\s+", " ", creator).strip()
        if text and len(text) >= 3 and not re.search(r"\(?(arr|transcr|ed|edition|lyrics|word)", text, re.I):
            composer = text
            break
    return title, composer


def _pending(conn: pymysql.connections.Connection, args: argparse.Namespace) -> list[dict[str, object]]:
    where = ["r.xml_title IS NULL", "r.download_url IS NOT NULL", "r.download_url <> ''"]
    params: list[object] = []
    if args.provider:
        where.append("r.provider = %s")
        params.append(args.provider)
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


def _matches(index_title: str, xml_title: str) -> bool:
    index_tokens = _tokens(index_title)
    xml_tokens = _tokens(xml_title)
    if not index_tokens or not xml_tokens:
        return True  # sin datos suficientes para decidir
    return bool(index_tokens & xml_tokens)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="máximo de reps a abrir (0 = todas)")
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--provider", default="omr")
    parser.add_argument("--title-like", default=None)
    parser.add_argument("--apply", action="store_true", help="corrige index_works con el título/compositor interno")
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-user", default="osap2027")
    parser.add_argument("--db-password", default="2027osapdb")
    parser.add_argument("--db-api", default="osap-api")
    args = parser.parse_args()

    conn = _connect(args)
    try:
        _ensure_columns(conn)
        rows = _pending(conn, args)
        print(f"Pendientes de auditar: {len(rows)}")
        cur = conn.cursor()
        reviewed = mismatched = errors = 0
        for row in rows:
            try:
                resp = requests.get(
                    str(row["download_url"]),
                    headers={"User-Agent": _BROWSER_UA, "Accept": "*/*"},
                    timeout=90,
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}")
                xml_title, xml_composer = _xml_metadata(resp.content)
                cur.execute(
                    "UPDATE index_representations SET xml_title=%s, xml_composer=%s WHERE id=%s",
                    (xml_title or None, xml_composer or None, row["rep_id"]),
                )
                reviewed += 1
                if xml_title and not _matches(str(row["title"] or ""), xml_title):
                    mismatched += 1
                    print(
                        f"  DESAJUSTE work={row['work_id']} index={row['title']!r} "
                        f"xml={xml_title!r} xml_composer={xml_composer!r}"
                    )
                    if args.apply:
                        cur.execute(
                            "UPDATE index_works SET title=%s, composer_name=COALESCE(NULLIF(%s,''), composer_name) "
                            "WHERE id=%s",
                            (xml_title, xml_composer, row["work_id"]),
                        )
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"  [error] rep {row['rep_id']}: {type(exc).__name__} {str(exc)[:120]}")
            if args.sleep:
                time.sleep(args.sleep)
        print(f"Revisados: {reviewed}  desajustes: {mismatched}  errores: {errors}")
        if mismatched and not args.apply:
            print("DRY-RUN: usa --apply para corregir los títulos anunciados.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
