"""Siembra la tabla `providers` de la BD operativa desde los YAML de `providers/`.

Permite que el sistema de proveedores lea de la BD (dev) manteniendo los YAML como
fuente para siembra y para entornos aún no migrados (prod).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from pathlib import Path

    from src.osap.infrastructure.state.op_store import _MemoryStore


def _read(child: Path, name: str) -> dict[str, object]:
    path = child / name
    if not path.exists():
        return {}
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc if isinstance(doc, dict) else {}


def provider_config_from_dir(child: Path) -> dict[str, object] | None:
    if not child.is_dir() or not (child / "provider.yaml").exists():
        return None
    provider = _read(child, "provider.yaml")
    return {
        "provider": provider,
        "endpoints": _read(child, "endpoints.yaml"),
        "mapping": _read(child, "mapping.yaml"),
        "resources": _read(child, "resources.yaml"),
        "transforms": _read(child, "transforms.yaml"),
    }


def provider_description_from_dir(child: Path) -> dict[str, str] | None:
    """Lee la descripción multi-idioma del `provider.yaml` (clave `description`)."""
    if not child.is_dir() or not (child / "provider.yaml").exists():
        return None
    provider = _read(child, "provider.yaml")
    desc = provider.get("description")
    if isinstance(desc, dict):
        clean = {str(k): str(v) for k, v in desc.items() if isinstance(v, str)}
        return clean or None
    if isinstance(desc, str) and desc.strip():
        return {"en": desc.strip()}
    return None


def seed_providers(store: _MemoryStore, providers_root: Path, active_ids: set[str]) -> int:
    """Upserta cada proveedor YAML en la BD. Devuelve cuántos se sembraron.

    Cada fichero YAML del proveedor va a su propia columna (provider/endpoints/mapping/
    resources/transforms) para evitar el doble mantenimiento en un único `config` JSON.
    """
    count = 0
    for child in sorted(providers_root.iterdir()):
        config = provider_config_from_dir(child)
        if config is None:
            continue
        provider_doc = config["provider"]
        pid = str(provider_doc.get("id") or child.name) if isinstance(provider_doc, dict) else child.name
        name = str(provider_doc.get("name") or pid) if isinstance(provider_doc, dict) else pid
        base_url = provider_doc.get("base_url") if isinstance(provider_doc, dict) else None
        store.upsert_provider(
            pid,
            name,
            base_url=str(base_url) if base_url else None,
            wired=pid in active_ids,
            kind="yaml",
            config=config,
            description=provider_description_from_dir(child),
            endpoints=_as_section(config.get("endpoints")),
            mapping=_as_section(config.get("mapping")),
            resources=_as_section(config.get("resources")),
            transforms=_as_section(config.get("transforms")),
        )
        count += 1
    return count


def _as_section(value: object) -> dict[str, object] | None:
    return value if isinstance(value, dict) else None
