"""Integración con IndexNow: aviso inmediato a buscadores de URLs nuevas/actualizadas.

IndexNow (Bing, Yandex, Seznam, Naver…) permite notificar en el momento las URLs que han
cambiado, sin esperar a que los buscadores vuelvan a rastrear el sitemap. **No es Google**
(Google se gestiona por Search Console).

La prueba de identidad viaja en la propia clave: IndexNow descarga `{base}/{key}.txt` para
verificar que el emisor controla el host. Ese fichero vive en `web/public/{key}.txt`, de modo
que lo sirve el build del SPA en la raíz del dominio.

Este módulo es solo el transporte (payload + lotes + envío). La **selección** de URLs la
hacen los llamadores: `script/indexnow.py` lo usa como paso final del reindexado, enviando
las obras actualizadas recientemente.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
# Límite documentado por petición de IndexNow.
MAX_URLS_PER_REQUEST = 10_000


def indexnow_host(base_url: str) -> str:
    """Host (sin esquema ni barra) que IndexNow debe considerar verificado."""
    return urllib.parse.urlsplit(base_url).netloc


def indexnow_key_location(base_url: str, key: str) -> str:
    """URL pública del fichero de clave (`{base}/{key}.txt`), base sin barra final."""
    return f"{base_url.rstrip('/')}/{key}.txt"


def indexnow_payload(host: str, key: str, key_location: str, urls: Sequence[str]) -> dict[str, object]:
    """Cuerpo JSON de una petición IndexNow."""
    return {
        "host": host,
        "key": key,
        "keyLocation": key_location,
        "urlList": list(urls),
    }


def chunked(items: Iterable[str], size: int = MAX_URLS_PER_REQUEST) -> Iterator[list[str]]:
    """Trocea `items` en lotes de como máximo `size` (el último puede ser menor)."""
    batch: list[str] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def submit_batch(payload: dict[str, object], *, timeout: float = 30.0) -> int:
    """Envía un lote y devuelve el código HTTP (0 si falló la red). Best-effort."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        INDEXNOW_ENDPOINT,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (urllib.error.URLError, OSError):
        return 0


def submit_urls(
    urls: Iterable[str],
    *,
    host: str,
    key: str,
    base_url: str,
    timeout: float = 30.0,
) -> list[int]:
    """Envía `urls` a IndexNow en lotes. Devuelve el código de cada lote (0 = error de red).

    Nunca lanza por un fallo de red/HTTP: devuelve el código para que el llamador decida.
    """
    key_location = indexnow_key_location(base_url, key)
    return [
        submit_batch(indexnow_payload(host, key, key_location, batch), timeout=timeout)
        for batch in chunked(urls)
    ]
