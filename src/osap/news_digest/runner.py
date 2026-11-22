"""Ejecutor del boletín de noticias de OSAP (cron diario, idempotente por día)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from email.message import EmailMessage
from pathlib import Path

from src.osap.infrastructure.news.client import NewsClient, NewsUnavailableError
from src.osap.news_digest.clients import (
    SubscribersUnavailableError,
    fetch_subscribers,
    post_support_digest,
)
from src.osap.news_digest.models import DigestItem, normalize_topics
from src.osap.news_digest.render import render_digest


@dataclass
class RunReport:
    day: str
    dry_run: bool
    subscribers: int = 0
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    messages: list[dict[str, object]] = field(default_factory=list)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _item(raw: dict[str, object]) -> DigestItem | None:
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    return DigestItem(
        title=title,
        summary=str(raw.get("summary") or "").strip(),
        url=str(raw.get("url")) if raw.get("url") else None,
        publisher=str(raw.get("publisher")) if raw.get("publisher") else None,
        published_at=str(raw.get("published_at")) if raw.get("published_at") else None,
    )


def _eml(subject: str, recipient: str, text: str, html: str) -> bytes:
    message = EmailMessage()
    message["From"] = "OSAP <no-reply@openmusicrepository.com>"
    message["To"] = recipient
    message["Subject"] = subject
    message["X-OSAP-Digest"] = "news"
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    return message.as_bytes()


def run(
    *,
    day: date | None = None,
    dry_run: bool = True,
    user_id: str | None = None,
    out_dir: Path | None = None,
    limit: int = 8,
    days: int = 30,
) -> RunReport:
    run_day = day or datetime.now(UTC).date()
    report = RunReport(day=run_day.isoformat(), dry_run=dry_run)
    output = out_dir or Path("var") / "news-digest" / run_day.isoformat()
    if dry_run:
        output.mkdir(parents=True, exist_ok=True)

    subscribers = fetch_subscribers(
        base_url=_env("OSAP_AUTH_INTERNAL_URL", "http://127.0.0.1:8200"),
        token=_env("OSAP_INTERNAL_SERVICE_TOKEN"),
        user_id=user_id,
    )
    report.subscribers = len(subscribers)
    news = NewsClient(
        base_url=_env("OSAP_NEWS_API_BASE", "http://127.0.0.1:8401"),
        token=_env("OSAP_NEWS_API_TOKEN"),
    )

    for subscriber in subscribers:
        if not subscriber.topics:
            report.skipped += 1
            report.messages.append(
                {"user_id": subscriber.user_id, "status": "skipped", "reason": "sin temas"}
            )
            continue
        try:
            data = news.query(
                languages=subscriber.languages,
                topics=normalize_topics(subscriber.topics),
                limit=limit,
                days=days,
            )
            raw_items = data.get("items")
            items = [
                item
                for raw in (raw_items if isinstance(raw_items, list) else [])
                if isinstance(raw, dict) and (item := _item(raw)) is not None
            ]
            if not items:
                report.skipped += 1
                report.messages.append(
                    {"user_id": subscriber.user_id, "status": "skipped", "reason": "sin noticias"}
                )
                continue
            digest = render_digest(subscriber, items, language=subscriber.languages[0])
            dedupe_key = f"news:{run_day.isoformat()}:{subscriber.user_id}"
            record: dict[str, object] = {
                "user_id": subscriber.user_id,
                "email": subscriber.email,
                "languages": subscriber.languages,
                "topics": subscriber.topics,
                "items": len(items),
                "subject": digest.subject,
                "dedupe_key": dedupe_key,
            }
            if dry_run:
                stem = f"{subscriber.user_id}.eml"
                (output / stem).write_bytes(
                    _eml(digest.subject, subscriber.email, digest.text, digest.html)
                )
                record["status"] = "dry-run"
                record["file"] = str(output / stem)
            elif _env("OSAP_SUPPORT_INTERNAL_URL"):
                result = post_support_digest(
                    base_url=_env("OSAP_SUPPORT_INTERNAL_URL"),
                    token=_env("OSAP_INTERNAL_SERVICE_TOKEN"),
                    payload={
                        "user_id": subscriber.user_id,
                        "recipient_email": subscriber.email,
                        "subject": digest.subject,
                        "text": digest.text,
                        "html": digest.html,
                        "dedupe_key": dedupe_key,
                    },
                )
                status = str(result.get("status") or "sent")
                record["status"] = status
                if status in {"queued", "sent"}:
                    report.sent += 1
                else:
                    report.skipped += 1
            else:
                raise SubscribersUnavailableError(
                    "OSAP_SUPPORT_INTERNAL_URL no configurada; no se envía nada"
                )
            report.messages.append(record)
        except (NewsUnavailableError, SubscribersUnavailableError) as exc:
            report.failed += 1
            report.messages.append(
                {"user_id": subscriber.user_id, "status": "failed", "reason": str(exc)}
            )

    if dry_run:
        (output / "report.json").write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report



