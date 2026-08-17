#!/usr/bin/env python
"""Simulación proceso completo: storage → APP → respuestas.

Actúa como el lado STORAGE: lee works250.json, envía cada obra al endpoint de resolución
de la APP (POST /api/v1/works/resolve), hace polling de la sesión y escribe las respuestas
en un fichero + resumen. El resultado puede pasarse al ingestor de la tabla de proveedores.

Uso:
    python script/simulate_storage_call.py [--base http://127.0.0.1:8001] \
        [--in script/works250.json] [--out script/storage_responses.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

_INPUT = Path(__file__).resolve().parent / "works250.json"
_OUT = Path(__file__).resolve().parent / "storage_responses.json"
_POLL_INTERVAL = 2.0
_MAX_WAIT = 120.0


def _resolve(work: dict[str, object], base: str) -> dict[str, object]:
    payload: dict[str, Any] = {}
    work_dict = work.get("work")
    if isinstance(work_dict, dict) and work_dict.get("title"):
        payload["works"] = [
            {"id": work.get("id"), "work": work.get("work"), "composer": work.get("composer")}
        ]
    resp = requests.post(f"{base}/api/v1/works/resolve", json=payload, timeout=30)
    if resp.status_code != 202:
        return {"id": work.get("id"), "status": "error", "http": resp.status_code, "incidents": [resp.text[:120]]}
    session_id = resp.json().get("data", {}).get("session_id")
    # Polling de la sesión (simula storage esperando a que APP/worker resuelva).
    waited = 0.0
    while waited < _MAX_WAIT:
        r = requests.get(f"{base}/api/v1/sessions/{session_id}/results", timeout=30)
        if r.status_code == 200:
            data = r.json().get("data", {})
            if data.get("status") in ("complete", "partial", "failed", "expired") or data.get("results"):
                return {"id": work.get("id"), "session_id": session_id, "data": data}
        time.sleep(_POLL_INTERVAL)
        waited += _POLL_INTERVAL
    return {"id": work.get("id"), "session_id": session_id, "status": "timeout"}


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8001")
    parser.add_argument("--in", dest="input", type=Path, default=_INPUT)
    parser.add_argument("--out", type=Path, default=_OUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    doc = json.loads(args.input.read_text(encoding="utf-8"))
    works = doc if isinstance(doc, list) else doc.get("works", [])
    if args.limit:
        works = works[: args.limit]

    responses: list[dict[str, object]] = []
    for w in works:
        res = _resolve(w, args.base)
        responses.append(res)
        print(f"[{res.get('id')}] {res.get('status')} session={res.get('session_id')}")
        time.sleep(0.3)

    args.out.write_text(json.dumps(responses, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for r in responses if r.get("status") in ("complete", "partial", "resolved", "ambiguous"))
    print(f"\n{len(responses)} peticiones -> {ok} completadas. Guardado en {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
