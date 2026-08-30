"""Seed the three missing providers into the database."""

import sys
sys.path.insert(0, 'src')

from pathlib import Path
from osap.infrastructure.state.op_store import build_op_store
from osap.infrastructure.providers.adapters.generic_provider_adapter import load_definition

# Correct path to providers directory
providers_root = Path(__file__).resolve().parent / "providers"
store = build_op_store('127.0.0.1', 'osap2027', '2027osapdb', 'osap-api')

# The three missing providers
missing = ["zenodo", "hymnary", "iiif"]

for provider_id in missing:
    provider_dir = providers_root / provider_id
    if not (provider_dir / "provider.yaml").exists():
        print(f"WARNING: {provider_id}: provider.yaml not found in {provider_dir}")
        continue
    
    # Load definition from YAML - returns ProviderDefinition dataclass
    definition = load_definition(provider_dir)
    
    # ProviderDefinition is a dataclass, access fields as attributes
    provider_id_key = definition.id
    name = definition.name
    base_url = definition.base_url
    endpoints = {k: {"method": v.method, "path": v.path, "query": v.query} 
                 for k, v in definition.endpoints.items()}
    mapping = definition.work_mapping
    resources = definition.resource_mapping
    
    # Upsert in DB
    store.upsert_provider(
        provider_id=definition.id,
        name=definition.name,
        base_url=definition.base_url,
        wired=True,
        kind="dynamic",
        config={
            "id": definition.id,
            "name": definition.name,
            "base_url": definition.base_url,
        },
        description={},
        endpoints={k: {"method": v.method, "path": v.path, "query": v.query} 
                   for k, v in definition.endpoints.items()},
        mapping=definition.work_mapping,
        resources=definition.resource_mapping,
        transforms={},
    )
    print(f"OK: {definition.id} ({definition.name}) upserted (wired=True)")

print("DONE: Seed completed")