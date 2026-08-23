"""Extraer `mbdump/work` y `mbdump/l_artist_work` del dump oficial de MusicBrainz.

El tar.bz2 (~7 GB, ~34 GB descomprimido) contiene decenas de tablas; solo interesan
estas dos para el indexador. Python tarfile con `extractfile` lee el miembro en
streaming y lo copia a disco sin descomprimir el resto.
"""

import os
import shutil
import sys
import tarfile

TAR = r"K:\DiscoD\Proyectos\AI_OSAP\osap-compositores\Carga\mbdump.tar.bz2"
OUT = r"K:\DiscoD\Proyectos\AI_OSAP\osap-compositores\Carga\musicbrainz_dump\mbdump"
WANT = {"mbdump/work", "mbdump/l_artist_work"}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(OUT, exist_ok=True)
    found: set[str] = set()
    with tarfile.open(TAR, "r:bz2") as tf:
        for member in tf:
            name = member.name
            if name not in WANT:
                continue
            target = os.path.join(OUT, os.path.basename(name))
            print(f"extrayendo {name} -> {target}", flush=True)
            with tf.extractfile(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1 << 20)
            found.add(name)
            print(f"  ok: {os.path.basename(name)} "
                  f"{round(os.path.getsize(target) / 1e6, 1)} MB", flush=True)
            if found == WANT:
                break
    missing = WANT - found
    print("faltan:", sorted(missing) if missing else "ninguno", flush=True)
    print("EXTRACCION_OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
