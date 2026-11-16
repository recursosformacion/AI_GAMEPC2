"""CLI del cron de noticias: `python -m src.osap.news_digest`."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from src.osap.news_digest.runner import run


def main() -> int:
    parser = argparse.ArgumentParser(description="Boletín diario de noticias de OSAP")
    parser.add_argument("--date", type=date.fromisoformat, default=None)
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--send", action="store_true", help="Entrega real vía osap-support")
    args = parser.parse_args()

    report = run(
        day=args.date,
        dry_run=not args.send,
        user_id=args.user_id,
        out_dir=args.out,
        limit=args.limit,
        days=args.days,
    )
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
