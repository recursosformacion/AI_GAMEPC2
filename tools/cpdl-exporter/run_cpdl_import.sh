#!/bin/bash
set -euo pipefail
STORAGE_DIR="$HOME/openmusicrepository.com/osap-storage"
DUMP="$HOME/cpdl_dump"
cd "$STORAGE_DIR"

echo "[cpdl] convirtiendo JSON -> XML"
.venv/bin/python /home/ocw/convert_cpdl_parts.py "$DUMP/cpdl-parts.json" "$DUMP"

echo "[cpdl] importando (upsert incremental, sin DELETE)"
.venv/bin/python -m scripts.import_cpdl_works --db osap_storage --dir "$DUMP"

echo "[cpdl] hecho. El index-sync (omr,cpdl,mutopia) lo recogera en <=30 min."
