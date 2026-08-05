"""Parser: ¿qué campos saco de un título?

Extrae los elementos estructurados (catálogo, número, tonalidad, opus) de un
título, SIN modificar el título original. Es la fase 1 del laboratorio.
"""

from __future__ import annotations

from src.osap.application.metadata_parser import ExtractedMetadata, extract_metadata

__all__ = ["extract_metadata", "ExtractedMetadata"]


def parse(title: str) -> ExtractedMetadata:
    """Extrae los metadatos estructurados de un título (no lo modifica)."""
    return extract_metadata(title)
