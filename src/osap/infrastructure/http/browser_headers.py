"""User-Agent compartido para llamadas salientes a storage/CDN (Cloudflare).

Cloudflare (dominio propio de R2, p. ej. `storage.openmusicrepository.com` y
`cdn.openmusicrepository.com`) responde **403** a User-Agents de librería
(`python-requests/*`, `urllib`, `curl`). Las llamadas server-side de osap-api deben
presentarse con un UA de navegador; si no, fallan búsquedas (CPDL), descargas y
adquisiciones.
"""

from __future__ import annotations

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def browser_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Cabeceras con UA de navegador; `extra` añade/sobrescribe (p. ej. Accept, Authorization)."""
    headers = {"User-Agent": BROWSER_USER_AGENT}
    if extra:
        headers.update(extra)
    return headers
