import sys
sys.path.insert(0, 'src')
from osap.infrastructure.state.op_store import build_op_store

store = build_op_store('127.0.0.1', 'osap2027', '2027osapdb', 'osap-api')
for p in store.list_providers():
    print(f'{p["provider_id"]}: {p["name"]} (wired={p["wired"]})')