#!/usr/bin/env python
"""Construir índice de compositores desde el dump JSON de MusicBrainz (artists).

Formato real: `artist.tar.xz` contiene `mbdump/artist`, un JSONL (una entidad por línea).
Lee esa entrada en streaming, filtra personas (type=Person) con ISNI/nombre, y construye
un índice {clave_canónica: [candidatos con isni/aliases/MBID]} en JSON.

Autocontenido (normalización inline) para correr en el VPS sin el repo.

Uso: python3 build_composer_index.py [--in artist.tar.xz] [--out composers_index.json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tarfile
from collections import defaultdict

_ANON = {
    "anon", "anon.", "anonymous", "trad", "trad.", "traditional",
    "attrib.", "attributed", "attrib", "unknown", "author unknown",
    "urheber unbekannt", "urheber unbek.",
}


def composer_key(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    low = text.lower()
    if low in _ANON or low.startswith("urheber unbekannt"):
        return "anonymous"
    text = re.sub(r"\s+\d{3,4}\s*$", "", text)  # años sueltos
    text = re.sub(r"\([^)]*\)", "", text)
    tokens = [t for t in text.split() if t]
    if not tokens:
        return ""
    last = tokens[-1].lower()
    firsts = "".join(t[0].lower() for t in tokens[:-1] if t[0].isalnum())
    return f"{firsts} {last}".strip()


def build(tar_path: str, out_path: str) -> None:
    index: dict[str, list[dict[str, object]]] = defaultdict(list)
    n = 0
    with tarfile.open(tar_path, "r:xz") as tf:
        member = next((m for m in tf if m.name.endswith("mbdump/artist") and m.isfile()), None)
        if member is None:
            print("No se encontró 'mbdump/artist' en el tar", file=sys.stderr)
            return
        f = tf.extractfile(member)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(data, dict) or data.get("type") != "Person":
                continue
            name = data.get("name")
            isni = data.get("isni") or []
            if not name and not isni:
                continue
            key = composer_key(str(name or ""))
            if not key:
                continue
            index[key].append(
                {
                    "mbid": data.get("id"),
                    "name": name,
                    "sort_name": data.get("sort-name"),
                    "isni": [str(i) for i in isni],
                    "aliases": [
                        str(a.get("name")) for a in (data.get("aliases") or [])
                        if isinstance(a, dict) and a.get("name")
                    ][:20],
                }
            )
            n += 1
            if n % 200000 == 0:
                print(f"{n} personas, {len(index)} claves", flush=True)

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)
    print(f"\nÍNDICE: {len(index)} claves, {n} personas -> {out_path} "
          f"({os.path.getsize(out_path)/1024/1024:.0f} MB)", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="tar_path", default="artist.tar.xz")
    parser.add_argument("--out", dest="out_path", default="composers_index.json")
    args = parser.parse_args()
    build(args.tar_path, args.out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
