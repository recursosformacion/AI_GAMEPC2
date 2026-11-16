"""Render del boletín en texto y HTML (OSAP es el propietario del correo)."""

from __future__ import annotations

from html import escape
from urllib.parse import urlsplit

from src.osap.news_digest.models import Digest, DigestItem, Subscriber

_LABELS = {
    "es": ("Noticias musicales para ti", "Leer", "Fuente"),
    "ca": ("Notícies musicals per a tu", "Llegir", "Font"),
    "fr": ("Actualités musicales pour vous", "Lire", "Source"),
    "en": ("Music news for you", "Read", "Source"),
    "de": ("Musiknachrichten für dich", "Lesen", "Quelle"),
    "it": ("Notizie musicali per te", "Leggi", "Fonte"),
    "pt": ("Notícias musicais para si", "Ler", "Fonte"),
}


def _label(language: str, index: int) -> str:
    return _LABELS.get(language, _LABELS["es"])[index]


def _safe_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme in {"http", "https"} else None


def render_digest(subscriber: Subscriber, items: list[DigestItem], *, language: str) -> Digest:
    title = _label(language, 0)
    name = subscriber.name or subscriber.email.split("@", 1)[0]
    subject = f"{title} · {len(items)}"

    lines = [f"Hola {name},", "", title, ""]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item.title}")
        if item.summary:
            lines.append(f"   {item.summary}")
        meta = " · ".join(part for part in (item.publisher, item.published_at) if part)
        if meta:
            lines.append(f"   {meta}")
        if item.url:
            lines.append(f"   {_label(language, 1)}: {item.url}")
        lines.append("")
    lines.append("— OSAP · Open Music Repository")
    text = "\n".join(lines)

    cards: list[str] = []
    for item in items:
        meta = " · ".join(escape(part) for part in (item.publisher, item.published_at) if part)
        link = _safe_url(item.url)
        action = (
            f'<p><a href="{escape(link)}">{escape(_label(language, 1))} →</a></p>'
            if link
            else ""
        )
        cards.append(
            "<article style=\"margin:0 0 18px;padding:0 0 14px;border-bottom:1px solid #e5e5e5\">"
            f"<h2 style=\"font-size:17px;margin:0 0 6px\">{escape(item.title)}</h2>"
            f"<p style=\"margin:0 0 6px;color:#444\">{escape(item.summary)}</p>"
            f"<p style=\"margin:0;color:#777;font-size:12px\">{meta}</p>{action}</article>"
        )
    html = (
        "<!doctype html><html><body style=\"margin:0;background:#f7f4ee;padding:24px;"
        "font-family:Georgia,serif;color:#243b35\">"
        "<div style=\"max-width:640px;margin:0 auto;background:#fff;padding:24px;"
        "border:1px solid #e5e5e5\">"
        f"<p style=\"letter-spacing:.12em;font-size:11px;color:#8a6d3b\">OSAP · CHORUS</p>"
        f"<h1 style=\"font-size:24px;margin:6px 0 18px\">{escape(title)}</h1>"
        f"<p>Hola {escape(name)},</p>{''.join(cards)}"
        "<p style=\"font-size:12px;color:#777\">Recibes este correo porque lo autorizaste en tu "
        "cuenta de OSAP. Puedes desactivarlo en cualquier momento.</p>"
        "</div></body></html>"
    )
    return Digest(
        subscriber=subscriber,
        items=items,
        subject=subject,
        text=text,
        html=html,
    )
