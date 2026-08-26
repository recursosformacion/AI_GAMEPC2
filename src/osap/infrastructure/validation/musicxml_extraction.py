"""Extracción de contenido MusicXML desde una representación de entrada.

Soporta:
  * XML plano (`str` o `bytes` con UTF-8),
  * `.mxl` (zip opcional con `META-INF/container.xml` apuntando al MusicXML,
    o el XML directamente en la raíz del zip).

La extracción NO valida: solo normaliza la entrada a un `str` con el XML del
score, y deja que el validador decida si es bien formado y utilizable.
"""

from __future__ import annotations

import io
import zipfile


class MusicXmlExtractionError(Exception):
    """La entrada no contiene un MusicXML extraíble (zip inválido, sin XML...)."""


def extract_musicxml(content: object) -> str:
    """Devuelve el texto XML del score desde `content` (str, bytes o zip)."""
    if content is None:
        raise MusicXmlExtractionError("sin contenido")

    # 1) bytes: probar zip (mxl) primero, luego XML plano.
    if isinstance(content, (bytes, bytearray, memoryview)):
        raw = bytes(content)
        if _looks_like_zip(raw):
            return _from_zip(raw)
        return _from_plain(raw)

    # 2) str: XML plano (o, si es un path, se intenta leer — no se asume).
    if isinstance(content, str):
        text = content.strip()
        if _looks_like_zip_text(text):
            return _from_zip_text(text)
        return text

    # 3) otro tipo (p. ej. un Path): no se soporta aquí.
    raise MusicXmlExtractionError(f"tipo de contenido no soportado: {type(content).__name__}")


def _looks_like_zip(raw: bytes) -> bool:
    return raw.startswith(b"PK\x03\x04") or raw.startswith(b"PK\x05\x06") or raw.startswith(b"PK\x07\x08")


def _looks_like_zip_text(text: str) -> bool:
    return text.lstrip().startswith("PK")


def _from_zip(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            return _pick_xml_from_zip(zf)
    except zipfile.BadZipFile as exc:
        raise MusicXmlExtractionError(f"zip inválido: {exc}") from exc


def _from_zip_text(text: str) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(text.encode("latin-1"))) as zf:
            return _pick_xml_from_zip(zf)
    except (zipfile.BadZipFile, UnicodeEncodeError) as exc:
        raise MusicXmlExtractionError(f"zip inválido: {exc}") from exc


def _pick_xml_from_zip(zf: zipfile.ZipFile) -> str:
    names = zf.namelist()

    # 1) container.xml indica el rootfile.
    if "META-INF/container.xml" in names:
        container = zf.read("META-INF/container.xml").decode("utf-8", "replace")
        import re

        m = re.search(r'full-path\s*=\s*"([^"]+)"', container)
        if m:
            target = m.group(1).strip()
            if target in names:
                return zf.read(target).decode("utf-8", "replace")

    # 2) XML en la raíz (nombre no META-INF).
    candidates = [n for n in names if n.endswith((".xml", ".musicxml")) and not n.startswith("META-INF/")]
    if not candidates:
        raise MusicXmlExtractionError("el zip no contiene ningún MusicXML")
    # Preferir el que no es container; si hay varios, el más corto (el principal).
    candidates.sort(key=len)
    return zf.read(candidates[0]).decode("utf-8", "replace")


def _from_plain(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "iso-8859-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise MusicXmlExtractionError("encoding no reconocido (ni UTF-8 ni ISO-8859-1)")
