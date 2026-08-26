"""Genera y guarda la biografía de Mozart en producción (reintento puntual)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

import composer_review_ai as bio

MOZART_ID = "add4410c-f0ff-46c7-a73e-84ab24518c28"


async def main() -> None:
    storage_root = Path(__file__).resolve().parent.parent
    cfg_path = storage_root / "config.yaml"
    db_config = bio.load_config(cfg_path)
    conn = await bio.get_connection(db_config)
    try:
        await bio.ensure_bio_table(conn)
        analysis = await bio.analyze_composer_async("Wolfgang Amadeus Mozart")
        print("is_composer:", analysis.get("is_composer"))
        print("confidence:", analysis.get("confidence"))
        bio_data = analysis.get("biography")
        if not bio_data:
            print("SIN biografía generada (None)")
            return
        await bio.upsert_biography(conn, MOZART_ID, bio_data)
        await bio.update_composer_review(
            conn, MOZART_ID, "reviewed", "Revisado por IA - DeepSeek V4", None,
        )
        await bio._set_active(conn, MOZART_ID)
        print("Biografía guardada.")
        print("summary:", (bio_data.get("summary") or "")[:120])
        print("era:", bio_data.get("era"), "| nationality:", bio_data.get("nationality"))
        print("key_works:", bio_data.get("key_works"))
        print("key_fact:", (bio_data.get("key_fact") or "")[:120])
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
