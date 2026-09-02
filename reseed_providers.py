"""Re-seed de proveedores desde YAML con mapping CRUDO.

El seed anterior guardó `definition.work_mapping` (procesado), que para algunos
proveedores quedó vacío. `load_definition_from_config` espera el mapping crudo
(`{"work": {...}, "resources": {...}}`) tal como está en los YAML.

Este script lee los YAML de `providers/{id}/` y hace upsert en la BD con el formato
correcto. Por defecto deja los proveedores en `wired=False` (preparados, no activos).
No modifica proveedores existentes funcionales (imslp, etc.) a menos que se incluyan
explícitamente en `IDS`.
"""

import sys
import yaml

sys.path.insert(0, "src")

from pathlib import Path

from osap.infrastructure.state.op_store import build_op_store

PROVIDERS_ROOT = Path(__file__).resolve().parent / "providers"
store = build_op_store("127.0.0.1", "osap2027", "2027osapdb", "osap-api")

IDS = ("hymnary", "zenodo", "iiif")


def _load(pid: str, name: str) -> dict[str, object]:
    d = PROVIDERS_ROOT / pid
    return yaml.safe_load((d / name).read_text(encoding="utf-8"))


for pid in IDS:
    provider_doc = _load(pid, "provider.yaml")
    endpoints_doc = _load(pid, "endpoints.yaml")
    mapping_doc = _load(pid, "mapping.yaml")
    resources_doc = _load(pid, "resources.yaml")

    store.upsert_provider(
        provider_id=pid,
        name=str(provider_doc.get("name") or pid),
        base_url=provider_doc.get("base_url"),
        wired=False,
        kind="dynamic",
        config=provider_doc,
        description=provider_doc.get("description", {}),
        endpoints=endpoints_doc,
        mapping=mapping_doc,
        resources=resources_doc,
        transforms={},
    )
    print(f"OK: {pid} re-seeded (mapping crudo: {list(mapping_doc.keys())})")

print("DONE")
