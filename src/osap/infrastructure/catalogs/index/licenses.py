"""Normalización de las licencias declaradas en storage.

El índice solo almacena conceptos buscables; la licencia vive en
`representations.representations_license` (edición) y `works.works_license`
(obra). Aquí se traducen los valores heredados de PDMX/CPDL a una etiqueta y una
URL, y se decide qué fuente prevalece.

Resumen de reglas:
- `representations_license` manda cuando es una licencia reconocible.
- Si es un marcador de corpus (`PDMX`) o un valor sucio, se usa `works_license`.
- Los valores no reconocidos se descartan (la UI mostrará «no indicada») antes que
  inventar una licencia.
"""

from __future__ import annotations

import re
from typing import Any

CC_BASE = "https://creativecommons.org"
CPDL_LICENSE_URL = "https://www.cpdl.org/wiki/index.php/CPDL:Licensing"

# Marcadores que no son licencias por sí mismos.
_NOT_LICENSES = {"pdmx", "religious", "personal?"}

_CC_URLS = {
    "cc by 4.0": f"{CC_BASE}/licenses/by/4.0/",
    "cc by-sa 4.0": f"{CC_BASE}/licenses/by-sa/4.0/",
    "cc by-nc 4.0": f"{CC_BASE}/licenses/by-nc/4.0/",
    "cc by-nc-sa 4.0": f"{CC_BASE}/licenses/by-nc-sa/4.0/",
    "cc by-nc-nd 4.0": f"{CC_BASE}/licenses/by-nc-nd/4.0/",
    "cc0 1.0": f"{CC_BASE}/publicdomain/zero/1.0/",
}


def _clean(raw: str | None) -> str:
    text = (raw or "").replace("\ufffd", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .;,-")


def normalize_license(raw: str | None) -> tuple[str, str | None] | None:
    """Devuelve `(etiqueta, url)` o `None` si el valor no es una licencia."""
    text = _clean(raw)
    if not text:
        return None
    low = text.casefold()
    if low in {"pdmx", "religious"}:
        return None
    if "publicdomain" in low.replace(" ", "") or "public domain" in low:
        return ("Dominio público", None)
    if low in {"cc-zero", "cc0", "cc0 1.0"} or "cc0" in low:
        return ("CC0 1.0", _CC_URLS["cc0 1.0"])
    if low == "cpdl":
        return ("Licencia CPDL", CPDL_LICENSE_URL)
    if low.startswith("personal"):
        return ("Licencia personal del editor", None)
    if "creative commons" in low and "attribution" in low:
        if "non-commercial" in low or "noncommercial" in low:
            if "no derivatives" in low or "noderiv" in low:
                label = "CC BY-NC-ND 4.0"
            elif "share alike" in low or "sharealike" in low:
                label = "CC BY-NC-SA 4.0"
            else:
                label = "CC BY-NC 4.0"
        elif "share alike" in low or "sharealike" in low:
            label = "CC BY-SA 4.0"
        else:
            label = "CC BY 4.0"
        return (label, _CC_URLS.get(label.casefold()))
    # Un texto libre no es una licencia fiable: mejor no etiquetar.
    return None


def resolve_license(
    representation_license: str | None,
    work_license: str | None,
) -> dict[str, Any] | None:
    """Elige la licencia de la representación con respaldo de la obra."""
    rep = normalize_license(representation_license)
    if rep is not None:
        return {
            "license": rep[0],
            "license_url": rep[1],
            "license_source": "representation",
            "license_raw": _clean(representation_license),
        }
    work = normalize_license(work_license)
    if work is not None:
        return {
            "license": work[0],
            "license_url": work[1],
            "license_source": "works",
            "license_raw": _clean(work_license),
        }
    return None
